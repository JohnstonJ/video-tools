"""Model classes for working with date DIF packs."""

from __future__ import annotations

import ctypes
import datetime
import re
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, NamedTuple

import video_tools.dv.data_util as du
import video_tools.dv.file.info as dv_file_info

from .base import CSVFieldMap, Pack, Type, ValidationError

_generic_date_pattern = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$")
_time_zone_pattern = re.compile(r"^(?P<hour>\d{2}):(?P<minute>\d{2})$")


class Week(IntEnum):
    SUNDAY = 0x0
    MONDAY = 0x1
    TUESDAY = 0x2
    WEDNESDAY = 0x03
    THURSDAY = 0x4
    FRIDAY = 0x5
    SATURDAY = 0x6


class DaylightSavingTime(IntEnum):
    DST = 0x0
    NORMAL = 0x1


# Generic date base class: several pack types share the same common date fields.  This class
# abstracts these details.
# See the derived classes for references to the standards.
@dataclass(frozen=True, kw_only=True)
class GenericDate(Pack):
    # The year field is a regular 4-digit field for ease of use.
    # However, the subcode only encodes a 2-digit year; we use 75 as the Y2K rollover threshold:
    # https://github.com/MediaArea/MediaInfoLib/blob/abdbb218b07f6cc0d4504c863ac5b42ecfab6fc6/Source/MediaInfo/Multiple/File_DvDif_Analysis.cpp#L1225
    year: int | None = None
    month: int | None = None
    day: int | None = None
    week: Week | None = None

    # Time zone information
    time_zone_hours: int | None = None
    time_zone_30_minutes: bool | None = None
    daylight_saving_time: DaylightSavingTime | None = None

    # Reserved bits (normally 0x3)
    reserved: int | None = None

    class MainFields(NamedTuple):  # Formats as yyyy/mm/dd
        year: int | None
        month: int | None
        day: int | None

    class WeekFields(NamedTuple):
        week: Week | None

    class TimeZoneFields(NamedTuple):  # Formats as hh:mm
        time_zone_hours: int | None
        time_zone_30_minutes: bool | None

    class DaylightSavingTimeFields(NamedTuple):
        daylight_saving_time: DaylightSavingTime | None

    class ReservedFields(NamedTuple):
        reserved: int | None

    text_fields: ClassVar[CSVFieldMap] = {
        None: MainFields,
        "week": WeekFields,
        "tz": TimeZoneFields,
        "dst": DaylightSavingTimeFields,
        "reserved": ReservedFields,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        # Date must be fully present or fully absent
        date_present = self.year is not None and self.month is not None and self.day is not None
        date_absent = self.year is None and self.month is None and self.day is None
        if (date_present and date_absent) or (not date_present and not date_absent):
            return "All main date fields must be fully present or fully absent."
        # No week if the date is absent
        if date_absent and self.week is not None:
            return "A weekday must not be provided if the date is otherwise absent."

        if date_present:
            # Assertion is to keep mypy happy at this point
            assert self.year is not None and self.month is not None and self.day is not None
            try:
                date_obj = datetime.date(year=self.year, month=self.month, day=self.day)
            except ValueError:
                return "The date field has an invalid range."
            if self.week is not None and date_obj.weekday() != int(self.week):
                return "The weekday is incorrect for the given date."
            if self.year >= 2075 or self.year < 1975:
                return "The year is too far into the future or the past."

        # Time zone offset parts must be fully present or fully absent.
        tz_present = (
            self.time_zone_hours is not None
            and self.time_zone_30_minutes is not None
            and self.daylight_saving_time is not None
        )
        tz_absent = (
            self.time_zone_hours is None
            and self.time_zone_30_minutes is None
            and self.daylight_saving_time is None
        )
        if (tz_present and tz_absent) or (not tz_present and not tz_absent):
            return "All main time zone fields must be fully present or fully absent."

        if self.time_zone_hours is not None and (
            self.time_zone_hours < 0 or self.time_zone_hours >= 24
        ):
            return "Time zone hours are out of range."

        if self.reserved is None:
            return "Reserved bits are required.  They should be 0x3 per the standard."
        if self.reserved < 0 or self.reserved > 0x3:
            return "Reserved bits are out of range."

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        match text_field:
            case None:
                match = None
                if text_value:
                    match = _generic_date_pattern.match(text_value)
                    if not match:
                        raise ValidationError(f"Parsing error while reading date {text_value}.")
                return cls.MainFields(
                    year=int(match.group("year")) if match else None,
                    month=int(match.group("month")) if match else None,
                    day=int(match.group("day")) if match else None,
                )
            case "week":
                return cls.WeekFields(
                    week=Week[text_value] if text_value else None,
                )
            case "tz":
                tz_hours = None
                tz_30_minutes = None
                if text_value:
                    match = _time_zone_pattern.match(text_value)
                    if not match:
                        raise ValidationError(
                            f"Parsing error while reading time zone {text_value}."
                        )
                    if match.group("minute") != "30" and match.group("minute") != "00":
                        raise ValidationError("Minutes portion of time zone must be 30 or 00.")
                    tz_hours = int(match.group("hour"))
                    tz_30_minutes = match.group("minute") == "30"
                return cls.TimeZoneFields(
                    time_zone_hours=tz_hours,
                    time_zone_30_minutes=tz_30_minutes,
                )
            case "dst":
                return cls.DaylightSavingTimeFields(
                    daylight_saving_time=DaylightSavingTime[text_value] if text_value else None,
                )
            case "reserved":
                return cls.ReservedFields(
                    reserved=int(text_value, 0) if text_value else None,
                )
            case _:
                assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        match text_field:
            case None:
                assert isinstance(value_subset, cls.MainFields)
                mv = value_subset
                return f"{mv.year:02}-{mv.month:02}-{mv.day:02}" if mv.year is not None else ""
            case "week":
                assert isinstance(value_subset, cls.WeekFields)
                return value_subset.week.name if value_subset.week is not None else ""
            case "tz":
                assert isinstance(value_subset, cls.TimeZoneFields)
                tzv = value_subset
                return (
                    f"{tzv.time_zone_hours:02}:{0 if not tzv.time_zone_30_minutes else 30:02}"
                    if tzv.time_zone_hours is not None
                    else ""
                )
            case "dst":
                assert isinstance(value_subset, cls.DaylightSavingTimeFields)
                return (
                    value_subset.daylight_saving_time.name
                    if value_subset.daylight_saving_time is not None
                    else ""
                )
            case "reserved":
                assert isinstance(value_subset, cls.ReservedFields)
                return (
                    du.hex_int(value_subset.reserved, 1)
                    if value_subset.reserved is not None
                    else ""
                )
            case _:
                assert False

    class _BinaryFields(ctypes.BigEndianStructure):
        _pack_ = 1
        _fields_: ClassVar = [
            ("ds", ctypes.c_uint8, 1),
            ("tm", ctypes.c_uint8, 1),
            ("tz_tens", ctypes.c_uint8, 2),
            ("tz_units", ctypes.c_uint8, 4),
            ("reserved", ctypes.c_uint8, 2),
            ("day_tens", ctypes.c_uint8, 2),
            ("day_units", ctypes.c_uint8, 4),
            ("week", ctypes.c_uint8, 3),
            ("month_tens", ctypes.c_uint8, 1),
            ("month_units", ctypes.c_uint8, 4),
            ("year_tens", ctypes.c_uint8, 4),
            ("year_units", ctypes.c_uint8, 4),
        ]

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> GenericDate | None:
        # Good starting points to look at:
        # IEC 61834-4:1998 9.3 Rec Date (Recording date) (VAUX)

        # The pack can be present, but all fields absent when the date is unknown.

        # Unpack fields from bytes and validate them.  Validation failures are
        # common due to tape dropouts.

        bin = cls._BinaryFields.from_buffer_copy(pack_bytes, 1)

        ds = None
        tm = None
        tz_tens = None
        tz_units = None
        # Time zone fields are all present or all absent
        if bin.tz_tens != 0x3 or bin.tz_units != 0xF:
            ds = bin.ds
            tm = bin.tm
            tz_tens = bin.tz_tens
            if tz_tens > 2:
                return None
            tz_units = bin.tz_units
            if tz_units > 9:
                return None

        day_tens = None
        day_units = None
        if bin.day_tens != 0x3 or bin.day_units != 0xF:
            day_tens = bin.day_tens
            day_units = bin.day_units
            if day_units > 9:
                return None

        month_tens = None
        month_units = None
        if bin.month_tens != 0x1 or bin.month_units != 0xF:
            month_tens = bin.month_tens
            month_units = bin.month_units
            if month_units > 9:
                return None

        year = None
        if bin.year_tens != 0xF or bin.year_units != 0xF:
            year_tens = bin.year_tens
            if year_tens > 9:
                return None
            year_units = bin.year_units
            if year_units > 9:
                return None
            year = year_tens * 10 + year_units
            year += 2000 if year < 75 else 1900

        return cls(
            year=year,
            month=(
                month_tens * 10 + month_units
                if month_tens is not None and month_units is not None
                else None
            ),
            day=(
                day_tens * 10 + day_units
                if day_tens is not None and day_units is not None
                else None
            ),
            week=Week(bin.week) if bin.week != 0x7 else None,
            time_zone_hours=(
                tz_tens * 10 + tz_units if tz_tens is not None and tz_units is not None else None
            ),
            time_zone_30_minutes=(
                (True if tm == 0 else False)
                if tz_tens is not None and tz_units is not None
                else None
            ),
            daylight_saving_time=(
                (DaylightSavingTime.DST if ds == 0 else DaylightSavingTime.NORMAL)
                if tz_tens is not None and tz_units is not None
                else None
            ),
            reserved=bin.reserved,
        )

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        # Good starting points to look at:
        # IEC 61834-4:1998 9.3 Rec Date (Recording date) (VAUX)
        assert self.reserved is not None  # assertion repeated from validate() to keep mypy happy
        short_year = self.year % 100 if self.year is not None else None
        struct = self._BinaryFields(
            ds=0x1 if self.daylight_saving_time != DaylightSavingTime.DST else 0x0,
            tm=0x1 if not self.time_zone_30_minutes else 0x00,
            tz_tens=int(self.time_zone_hours / 10) if self.time_zone_hours is not None else 0x3,
            tz_units=self.time_zone_hours % 10 if self.time_zone_hours is not None else 0xF,
            reserved=self.reserved,
            day_tens=int(self.day / 10) if self.day is not None else 0x3,
            day_units=self.day % 10 if self.day is not None else 0xF,
            week=int(self.week) if self.week is not None else 0x7,
            month_tens=int(self.month / 10) if self.month is not None else 0x1,
            month_units=self.month % 10 if self.month is not None else 0xF,
            year_tens=int(short_year / 10) if short_year is not None else 0xF,
            year_units=short_year % 10 if short_year is not None else 0xF,
        )
        return bytes([self.pack_type, *bytes(struct)])


# AAUX recording date
# IEC 61834-4:1998 8.3 Rec Date (AAUX)
@dataclass(frozen=True, kw_only=True)
class AAUXRecordingDate(GenericDate):
    pack_type = Type.AAUX_RECORDING_DATE


# VAUX recording date
# IEC 61834-4:1998 9.3 Rec Date (Recording date) (VAUX)
@dataclass(frozen=True, kw_only=True)
class VAUXRecordingDate(GenericDate):
    pack_type = Type.VAUX_RECORDING_DATE
