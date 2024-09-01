"""Model classes for working with timecode DIF packs."""

from __future__ import annotations

import ctypes
import datetime
import re
from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Any, ClassVar, cast

import video_tools.dv.data_util as du
import video_tools.dv.file.info as dv_file_info
from video_tools.typing import DataclassInstance

from .base import CSVFieldMap, Pack, Type, ValidationError


# Color frame
# SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
class ColorFrame(IntEnum):
    UNSYNCHRONIZED = 0x0
    SYNCHRONIZED = 0x1


# Biphase mark polarity correction
# SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
class PolarityCorrection(IntEnum):
    EVEN = 0x0
    ODD = 0x1


# Blank flag: determines whether a discontinuity exists prior to the
# absolute track number on the track where this pack is recorded
# IEC 61834-4:1998 4.4 Time Code (TITLE)
class BlankFlag(IntEnum):
    DISCONTINUOUS = 0x0
    CONTINUOUS = 0x1


_smpte_time_pattern = re.compile(
    r"^(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
    r"((?P<frame_separator>[:;])(?P<frame>\d{2}))?$"
)


# Generic timecode base class: several pack types share mostly the same common timecode fields,
# with only a very few minor variations.  This class abstracts these details.
# See the derived classes for references to the standards.
@dataclass(frozen=True, kw_only=True)
class GenericTimecode(Pack):
    hour: int | None = None
    minute: int | None = None
    second: int | None = None
    frame: int | None = None

    # The next four fields are defined as seen in SMPTE 306M, and in IEC 61834-4 when recording
    # BINARY packs.
    drop_frame: bool | None = None  # always True in IEC 61834-4 if no BINARY pack
    color_frame: ColorFrame | None = None  # overlaps with blank_flag in IEC 61834-4 if no bin pack
    polarity_correction: PolarityCorrection | None = None  # always 1 in IEC 61834-4 if no bin pack
    binary_group_flags: int | None = None  # always 0x7 in IEC 61834-4 if no BINARY pack

    # Some packs allow the pack to be present while the actual time fields are empty.
    # Derived classes can choose what is allowed.
    _time_required: ClassVar[bool]
    # Some packs allow frames to be omitted while the rest of the time is still present.
    # This variable controls the behavior.
    _frames_required: ClassVar[bool]

    @dataclass(frozen=True, kw_only=True)
    class MainFields:
        hour: int | None
        minute: int | None
        second: int | None
        frame: int | None
        drop_frame: int | None

    @dataclass(frozen=True, kw_only=True)
    class ColorFrameFields:
        color_frame: ColorFrame | None

    @dataclass(frozen=True, kw_only=True)
    class PolarityCorrectionFields:
        polarity_correction: PolarityCorrection | None

    @dataclass(frozen=True, kw_only=True)
    class BinaryGroupFlagsFields:
        binary_group_flags: int | None

    text_fields: ClassVar[CSVFieldMap] = {
        None: MainFields,
        "color_frame": ColorFrameFields,
        "polarity_correction": PolarityCorrectionFields,
        "binary_group_flags": BinaryGroupFlagsFields,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        # Main time part must be fully present or fully absent
        time_present = self.hour is not None and self.minute is not None and self.second is not None
        time_absent = self.hour is None and self.minute is None and self.second is None
        if (time_present and time_absent) or (not time_present and not time_absent):
            return "All main time fields must be fully present or fully absent."
        # Don't allow specifying frames if there's no other time
        if self.frame is not None and time_absent:
            return "Frame numbers cannot be given if the rest of the time is missing."

        # Apply additional requirements based on the derived class
        if self._time_required and time_absent:
            return "A time value is required but was not given."
        if time_present and self._frames_required and self.frame is None:
            return "A frame number must be given with the time value."

        # The remaining bits should always be here... physically, the bits are holding _something_
        if (
            self.drop_frame is None
            or self.color_frame is None
            or self.polarity_correction is None
            or self.binary_group_flags is None
        ):
            return "All auxiliary SMPTE timecode fields must be provided."

        # Check ranges of values
        if time_present:
            try:
                # Assertion is to keep mypy happy at this point
                assert self.hour is not None and self.minute is not None and self.second is not None
                datetime.time(hour=self.hour, minute=self.minute, second=self.second)
            except ValueError:
                return "The time field has an invalid range."

        if self.frame is not None:
            if self.frame < 0:
                return "A negative frame number was provided."
            if system == dv_file_info.DVSystem.SYS_525_60 and self.frame >= 30:
                return "The frame number is too high for the given NTSC frame rate."
            if system == dv_file_info.DVSystem.SYS_625_50 and self.frame >= 25:
                return "The frame number is too high for the given PAL/SECAM frame rate."
            if self.drop_frame and system == dv_file_info.DVSystem.SYS_625_50:
                # drop_frame only applies to NTSC.  But if the frame number is absent completely,
                # we'll skip this verification, since some packs might simply be leaving the bits
                # unconditionally set (who knows? I need to see more test data).
                return "The drop frame flag was set, but this does not make sense for PAL/SECAM."
            assert self.minute is not None and self.second is not None
            if self.drop_frame and self.minute % 10 > 0 and self.second == 0 and self.frame < 2:
                # should have dropped the frame
                return "The drop frame flag was set, but a dropped frame number was provided."

        if self.binary_group_flags < 0 or self.binary_group_flags > 0x7:
            return "Binary group flags are out of range."

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> DataclassInstance:
        match text_field:
            case None:
                match = None
                if text_value:
                    match = _smpte_time_pattern.match(text_value)
                    if not match:
                        raise ValidationError(f"Parsing error while reading timecode {text_value}.")
                return cls.MainFields(
                    hour=int(match.group("hour")) if match else None,
                    minute=int(match.group("minute")) if match else None,
                    second=int(match.group("second")) if match else None,
                    # frames are optional in this regex
                    frame=int(match.group("frame")) if match and match.group("frame") else None,
                    drop_frame=(
                        match.group("frame_separator") == ";"
                        if match and match.group("frame_separator")
                        # If the frames are missing, we'll just set the DF bit since that's how I've
                        # observed it happening in practice on a VAUX Rec Date pack from my camera.
                        # This is also the value we'd want to set if the time is missing completely.
                        else True
                    ),
                )
            case "color_frame":
                return cls.ColorFrameFields(
                    color_frame=ColorFrame[text_value] if text_value else None,
                )
            case "polarity_correction":
                return cls.PolarityCorrectionFields(
                    polarity_correction=PolarityCorrection[text_value] if text_value else None,
                )
            case "binary_group_flags":
                return cls.BinaryGroupFlagsFields(
                    binary_group_flags=int(text_value, 0) if text_value else None,
                )
            case _:
                assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: DataclassInstance) -> str:
        match text_field:
            case None:
                assert isinstance(value_subset, cls.MainFields)
                v = value_subset
                if v.hour is None:
                    return ""
                if v.frame is None:
                    return f"{v.hour:02}:{v.minute:02}:{v.second:02}"
                return (
                    f"{v.hour:02}:{v.minute:02}:{v.second:02};{v.frame:02}"
                    if v.drop_frame
                    else f"{v.hour:02}:{v.minute:02}:{v.second:02}:{v.frame:02}"
                )

            case "color_frame":
                assert isinstance(value_subset, cls.ColorFrameFields)
                return value_subset.color_frame.name if value_subset.color_frame is not None else ""
            case "polarity_correction":
                assert isinstance(value_subset, cls.PolarityCorrectionFields)
                return (
                    value_subset.polarity_correction.name
                    if value_subset.polarity_correction is not None
                    else ""
                )
            case "binary_group_flags":
                assert isinstance(value_subset, cls.BinaryGroupFlagsFields)
                return (
                    du.hex_int(value_subset.binary_group_flags, 1)
                    if value_subset.binary_group_flags is not None
                    else ""
                )
            case _:
                assert False

    class _BinaryFields(ctypes.BigEndianStructure):
        _pack_ = 1
        _fields_: ClassVar = [
            ("cf", ctypes.c_uint8, 1),
            ("df", ctypes.c_uint8, 1),
            ("frame_tens", ctypes.c_uint8, 2),
            ("frame_units", ctypes.c_uint8, 4),
            ("pc2_8", ctypes.c_uint8, 1),
            ("second_tens", ctypes.c_uint8, 3),
            ("second_units", ctypes.c_uint8, 4),
            ("pc3_8", ctypes.c_uint8, 1),
            ("minute_tens", ctypes.c_uint8, 3),
            ("minute_units", ctypes.c_uint8, 4),
            ("pc4_8", ctypes.c_uint8, 1),
            ("bgf1", ctypes.c_uint8, 1),
            ("hour_tens", ctypes.c_uint8, 2),
            ("hour_units", ctypes.c_uint8, 4),
        ]

    @classmethod
    def _do_parse_binary_generic_tc(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem, **init_kwargs: Any
    ) -> GenericTimecode | None:
        # Good starting points to look at:
        # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
        # IEC 61834-4:1998 4.4 Time Code (TITLE)
        # IEC 61834-4:1998 9.4 Rec Time (VAUX)
        # Also see SMPTE 12M

        # Unpack fields from bytes and validate them.  Validation failures are
        # common due to tape dropouts.

        bin = cls._BinaryFields.from_buffer_copy(pack_bytes, 1)

        frame_tens = None
        frame_units = None
        if bin.frame_tens != 0x3 or bin.frame_units != 0xF:
            frame_tens = bin.frame_tens
            if frame_tens > 2:
                return None
            frame_units = bin.frame_units
            if frame_units > 9:
                return None

        if system == dv_file_info.DVSystem.SYS_525_60:
            pc = bin.pc2_8
        elif system == dv_file_info.DVSystem.SYS_625_50:
            bgf0 = bin.pc2_8
        second_tens = None
        second_units = None
        if bin.second_tens != 0x7 or bin.second_units != 0xF:
            second_tens = bin.second_tens
            if second_tens > 5:
                return None
            second_units = bin.second_units
            if second_units > 9:
                return None

        if system == dv_file_info.DVSystem.SYS_525_60:
            bgf0 = bin.pc3_8
        elif system == dv_file_info.DVSystem.SYS_625_50:
            bgf2 = bin.pc3_8
        minute_tens = None
        minute_units = None
        if bin.minute_tens != 0x7 or bin.minute_units != 0xF:
            minute_tens = bin.minute_tens
            if minute_tens > 5:
                return None
            minute_units = bin.minute_units
            if minute_units > 9:
                return None

        if system == dv_file_info.DVSystem.SYS_525_60:
            bgf2 = bin.pc4_8
        elif system == dv_file_info.DVSystem.SYS_625_50:
            pc = bin.pc4_8
        hour_tens = None
        hour_units = None
        if bin.hour_tens != 0x3 or bin.hour_units != 0xF:
            hour_tens = bin.hour_tens
            if hour_tens > 2:
                return None
            hour_units = bin.hour_units
            if hour_units > 9:
                return None

        return cls(
            hour=(
                hour_tens * 10 + hour_units
                if hour_tens is not None and hour_units is not None
                else None
            ),
            minute=(
                minute_tens * 10 + minute_units
                if minute_tens is not None and minute_units is not None
                else None
            ),
            second=(
                second_tens * 10 + second_units
                if second_tens is not None and second_units is not None
                else None
            ),
            frame=(
                frame_tens * 10 + frame_units
                if frame_tens is not None and frame_units is not None
                else None
            ),
            drop_frame=bin.df == 1,
            color_frame=(ColorFrame.SYNCHRONIZED if bin.cf == 1 else ColorFrame.UNSYNCHRONIZED),
            polarity_correction=(PolarityCorrection.ODD if pc == 1 else PolarityCorrection.EVEN),
            binary_group_flags=(bgf2 << 2) | (bin.bgf1 << 1) | bgf0,
            **init_kwargs,
        )

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> GenericTimecode | None:
        return cls._do_parse_binary_generic_tc(pack_bytes, system)

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        # Good starting points to look at:
        # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
        # IEC 61834-4:1998 4.4 Time Code (TITLE)
        # IEC 61834-4:1998 9.4 Rec Time (VAUX)
        # Also see SMPTE 12M
        assert (  # assertion repeated from validate() to keep mypy happy
            self.drop_frame is not None
            and self.color_frame is not None
            and self.polarity_correction is not None
            and self.binary_group_flags is not None
        )
        pc = int(self.polarity_correction)
        bgf0 = self.binary_group_flags & 0x01
        bgf1 = (self.binary_group_flags & 0x02) >> 1
        bgf2 = (self.binary_group_flags & 0x04) >> 2
        struct = self._BinaryFields(
            cf=self.color_frame,
            df=self.drop_frame,
            frame_tens=int(self.frame / 10) if self.frame is not None else 0x3,
            frame_units=self.frame % 10 if self.frame is not None else 0xF,
            pc2_8=pc if system == dv_file_info.DVSystem.SYS_525_60 else bgf0,
            second_tens=int(self.second / 10) if self.second is not None else 0x7,
            second_units=self.second % 10 if self.second is not None else 0xF,
            pc3_8=bgf0 if system == dv_file_info.DVSystem.SYS_525_60 else bgf2,
            minute_tens=int(self.minute / 10) if self.minute is not None else 0x7,
            minute_units=self.minute % 10 if self.minute is not None else 0xF,
            pc4_8=bgf2 if system == dv_file_info.DVSystem.SYS_525_60 else pc,
            bgf1=bgf1,
            hour_tens=int(self.hour / 10) if self.hour is not None else 0x3,
            hour_units=self.hour % 10 if self.hour is not None else 0xF,
        )
        return bytes([self.pack_type, *bytes(struct)])

    def increment_frame(self, system: dv_file_info.DVSystem) -> GenericTimecode:
        """Return a copy with frame incremented by 1."""
        # Read current values and make sure they were present.  (Other field
        # values are allowed to be empty.)
        #
        # Note that at this time, we only support this operation on times that have frame numbers.
        h = self.hour
        m = self.minute
        s = self.second
        f = self.frame
        if h is None or m is None or s is None or f is None or self.drop_frame is None:
            raise ValidationError("Cannot increment a time pack with no time in it.")
        if self.drop_frame and system != dv_file_info.DVSystem.SYS_525_60:
            raise ValidationError(
                "Drop frame flag is set on PAL/SECAM video, which probably doesn't make sense."
            )

        # Increment values as appropriate
        f += 1
        if system == dv_file_info.DVSystem.SYS_525_60 and f == 30:
            s += 1
            f = 0
        elif system == dv_file_info.DVSystem.SYS_625_50 and f == 25:
            s += 1
            f = 0
        if s == 60:
            m += 1
            s = 0
        if m == 60:
            h += 1
            m = 0
        if h == 24:
            h = 0
            m = 0
            s = 0
            f = 0

        # Process drop frames
        if self.drop_frame and f <= 1 and s == 0 and m % 10 > 0:
            f = 2

        return replace(self, hour=h, minute=m, second=s, frame=f)


# Title timecode
# SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
# IEC 61834-4:1998 4.4 Time Code (TITLE)
# Also see SMPTE 12M
@dataclass(frozen=True, kw_only=True)
class TitleTimecode(GenericTimecode):
    # IEC 61834-4:1998 defines this field instead of the other SMPTE fields
    # when not recording TITLE BINARY pack.  In that scenario, the remaining
    # fields from SMPTE that don't overlap are always set to the highest bit
    # values possible, and the end-user should ensure that it is indeed the case.
    blank_flag: BlankFlag | None = None  # overlaps with color_frame from above

    _time_required = True
    _frames_required = True

    @dataclass(frozen=True, kw_only=True)
    class BlankFlagFields:
        blank_flag: BlankFlag | None

    text_fields: ClassVar[CSVFieldMap] = {
        **GenericTimecode.text_fields,
        "blank_flag": BlankFlagFields,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        base_validate = super().validate(system)
        if base_validate is not None:
            return base_validate

        # These two fields physically overlap for different use cases.
        if self.blank_flag is None:
            return "A value for the blank flag must be provided."
        assert self.color_frame is not None  # base class checks this
        if int(self.blank_flag) != int(self.color_frame):
            return (
                f"Blank flag integer value of {int(self.blank_flag)} must be equal to the color "
                f"frame flag integer value of {int(self.color_frame)}, because they occupy the "
                "same physical bit positions on the tape.  Change one value to match the other."
            )

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> DataclassInstance:
        if text_field == "blank_flag":
            return cls.BlankFlagFields(
                blank_flag=BlankFlag[text_value] if text_value else None,
            )
        return super().parse_text_value(text_field, text_value)

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: DataclassInstance) -> str:
        if text_field == "blank_flag":
            assert isinstance(value_subset, cls.BlankFlagFields)
            return value_subset.blank_flag.name if value_subset.blank_flag is not None else ""
        return super().to_text_value(text_field, value_subset)

    pack_type = Type.TITLE_TIMECODE

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> TitleTimecode | None:
        # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
        # IEC 61834-4:1998 4.4 Time Code (TITLE)
        # Also see SMPTE 12M

        # NOTE: CF bit is also BF bit in IEC 61834-4 if not
        # recording TITLE BINARY pack.
        bf = (pack_bytes[1] & 0x80) >> 7
        return cast(
            TitleTimecode,
            cls._do_parse_binary_generic_tc(
                pack_bytes,
                system,
                blank_flag=BlankFlag.CONTINUOUS if bf == 1 else BlankFlag.DISCONTINUOUS,
            ),
        )


# AAUX recording time
# IEC 61834-4:1998 8.4 Rec Time (AAUX)
# Also see SMPTE 12M
@dataclass(frozen=True, kw_only=True)
class AAUXRecordingTime(GenericTimecode):
    _time_required = False
    _frames_required = False

    pack_type = Type.AAUX_RECORDING_TIME


# VAUX recording time
# IEC 61834-4:1998 9.4 Rec Time (VAUX)
# Also see SMPTE 12M
@dataclass(frozen=True, kw_only=True)
class VAUXRecordingTime(GenericTimecode):
    _time_required = False
    _frames_required = False

    pack_type = Type.VAUX_RECORDING_TIME
