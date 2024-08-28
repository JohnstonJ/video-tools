"""Model classes for working with raw DIF data."""

from __future__ import annotations

import ctypes
import datetime
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, replace
from enum import IntEnum
from typing import Any, ClassVar, NamedTuple, cast

import video_tools.dv.data_util as du
import video_tools.dv.file_info as dv_file_info


class PackValidationError(ValueError):
    pass


# Pack types
# IEC 61834-4:1998
class PackType(IntEnum):
    # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
    # IEC 61834-4:1998 4.4 Time Code (TITLE)
    TITLE_TIMECODE = 0x13

    # SMPTE 306M-2002 Section 9.2.2 Binary group pack (BG)
    # IEC 61834-4:1998 4.5 Binary Group
    TITLE_BINARY_GROUP = 0x14

    # IEC 61834-4:1998 8.3 Rec Date (AAUX)
    AAUX_RECORDING_DATE = 0x52

    # IEC 61834-4:1998 8.4 Rec Time (AAUX)
    AAUX_RECORDING_TIME = 0x53

    # IEC 61834-4:1998 8.5 Binary Group (AAUX)
    AAUX_BINARY_GROUP = 0x54

    # IEC 61834-4:1998 9.3 Rec Date (Recording date) (VAUX)
    VAUX_RECORDING_DATE = 0x62

    # IEC 61834-4:1998 9.4 Rec Time (VAUX)
    VAUX_RECORDING_TIME = 0x63

    # IEC 61834-4:1998 9.5 Binary Group (VAUX)
    VAUX_BINARY_GROUP = 0x64

    # IEC 61834-4:1998 12.16 No Info: No information (SOFT MODE)
    # Also, very commonly a dropout - especially in the subcode DIF block
    NO_INFO = 0xFF


# NOTE:  Pack fields are often ultimately all required to be valid, but we allow them to
# be missing during intermediate transformations / in CSV files.  Validity checks are done
# when serializing to/from pack binary blobs.


CSVFieldMap = dict[str | None, type[NamedTuple]]


@dataclass(frozen=True, kw_only=True)
class Pack(ABC):
    @abstractmethod
    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        """Indicate whether the contents of the pack are fully valid.

        A fully valid pack can be safely written to a binary DV file.  When reading a binary
        DV file, this function is used to throw out corrupted packs.

        The return value contains a description of the validation failure.  If the pack passes
        validation, then None is returned.
        """
        pass

    # Abstract functions for converting subsets of pack values to/from strings suitable for use
    # in a CSV file or other configuration files.  Pack value subsets are a NamedTuple whose
    # field values must match the field values defined in the main dataclass.

    # Dict of text field names used when saving the pack to a CSV file.
    # The dictionary values are NamedTuple types for the subset of pack values that go into it.
    #
    # Special: if the text field name is None, then it's considered the default/main value for the
    # pack.  This affects prefixes that are prepended to the final CSV field name:
    #     field name of None --> sc_smpte_timecode
    #     field name of 'blank_flag' --> sc_smpte_timecode_blank_flag
    text_fields: ClassVar[CSVFieldMap]

    @classmethod
    @abstractmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        """Parse the value for a CSV text field name into a tuple of dataclass field values.

        The returned keys must match with keyword arguments in the initializer.
        """
        pass

    @classmethod
    @abstractmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        """Convert a subset of the pack field values to a single CSV text field value.

        The value_subset is what is returned by value_subset_for_text_field."""
        pass

    def value_subset_for_text_field(self, text_field: str | None) -> NamedTuple:
        """Returns a subset of dataclass field values that are used by the given text_field.

        The returned keys must match with keyword arguments in the initializer."""
        typ = self.text_fields[text_field]
        full_dict = asdict(self)
        subset_dict = {field_name: full_dict[field_name] for field_name in typ._fields}
        # For some reason, I can't figure out how to get mypy to think I'm invoking the type
        # initializer, rather than the NamedType builtin function itself...
        return cast(NamedTuple, typ(**subset_dict))  # type: ignore[call-overload]

    # Functions for converting all pack values to/from multiple CSV file fields.

    @classmethod
    def parse_text_values(cls, text_field_values: dict[str | None, str]) -> Pack:
        """Create a new instance of the pack by parsing text values.

        Any missing field values will be assumed to have a value of the empty string.
        """
        parsed_values: dict[str, Any] = {}
        for text_field, text_value in text_field_values.items():
            parsed_values |= cls.parse_text_value(text_field, text_value)._asdict()
        return cls(**parsed_values)

    def to_text_values(self) -> dict[str | None, str]:
        """Convert the pack field values to text fields."""
        result = {}
        for text_field in self.text_fields.keys():
            result[text_field] = self.to_text_value(
                text_field, self.value_subset_for_text_field(text_field)
            )
        return result

    # Functions for going to/from binary packs

    # Binary byte value for the pack type header.
    pack_type: ClassVar[PackType]

    @classmethod
    @abstractmethod
    def _do_parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> Pack | None:
        """The derived class should parse the bytes into a new Pack object.

        It does not need to assert the length of pack_bytes or assert that the pack type is indeed
        correct.  It also does not need to call pack.validate() and return None if it's invalid.
        The main parse_binary function does those common tasks for you.
        """

    @classmethod
    def parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> Pack | None:
        """Create a new instance of the pack by parsing a binary blob from a DV file.

        The input byte array is expected to be 5 bytes: pack type byte followed by 4 data bytes.
        """
        assert len(pack_bytes) == 5
        assert pack_bytes[0] == cls.pack_type
        pack = cls._do_parse_binary(pack_bytes, system)
        return pack if pack is not None and pack.validate(system) is None else None

    @abstractmethod
    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        """Convert this pack to binary; the pack can be assumed to be valid."""
        pass

    def to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        """Convert this pack to the 5 byte binary format."""
        validation_message = self.validate(system)
        if validation_message is not None:
            raise PackValidationError(validation_message)
        b = self._do_to_binary(system)
        assert len(b) == 5
        assert b[0] == self.pack_type
        return b


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

    class MainFields(NamedTuple):
        hour: int | None
        minute: int | None
        second: int | None
        frame: int | None
        drop_frame: int | None

    class ColorFrameFields(NamedTuple):
        color_frame: ColorFrame | None

    class PolarityCorrectionFields(NamedTuple):
        polarity_correction: PolarityCorrection | None

    class BinaryGroupFlagsFields(NamedTuple):
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
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        match text_field:
            case None:
                match = None
                if text_value:
                    match = _smpte_time_pattern.match(text_value)
                    if not match:
                        raise PackValidationError(
                            f"Parsing error while reading timecode {text_value}."
                        )
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
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
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
            raise PackValidationError("Cannot increment a time pack with no time in it.")
        if self.drop_frame and system != dv_file_info.DVSystem.SYS_525_60:
            raise PackValidationError(
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


# Generic SMPTE binary group base class: several pack types reuse the same structure.
# See the derived classes for references to the standards.
@dataclass(frozen=True, kw_only=True)
class GenericBinaryGroup(Pack):
    # this will always be 4 bytes
    value: bytes | None = None

    class MainFields(NamedTuple):
        value: bytes | None  # Formats as 8 hex digits

    text_fields: ClassVar[CSVFieldMap] = {None: MainFields}

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if self.value is None:
            return "A binary group value was not provided."
        if len(self.value) != 4:
            return (
                "The binary group has the wrong length: expected 4 bytes "
                f"but got {len(self.value)}."
            )
        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        assert text_field is None
        return cls.MainFields(
            value=bytes.fromhex(text_value.removeprefix("0x")) if text_value else None
        )

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        assert text_field is None
        assert isinstance(value_subset, cls.MainFields)
        return du.hex_bytes(value_subset.value) if value_subset.value is not None else ""

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> GenericBinaryGroup | None:
        return cls(value=bytes(pack_bytes[1:]))

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.value is not None  # assertion repeated from validate() to keep mypy happy
        return bytes(
            [
                self.pack_type,
                self.value[0],
                self.value[1],
                self.value[2],
                self.value[3],
            ]
        )


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
                        raise PackValidationError(f"Parsing error while reading date {text_value}.")
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
                        raise PackValidationError(
                            f"Parsing error while reading time zone {text_value}."
                        )
                    if match.group("minute") != "30" and match.group("minute") != "00":
                        raise PackValidationError("Minutes portion of time zone must be 30 or 00.")
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

    class BlankFlagFields(NamedTuple):
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
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        if text_field == "blank_flag":
            return cls.BlankFlagFields(
                blank_flag=BlankFlag[text_value] if text_value else None,
            )
        return super().parse_text_value(text_field, text_value)

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        if text_field == "blank_flag":
            assert isinstance(value_subset, cls.BlankFlagFields)
            return value_subset.blank_flag.name if value_subset.blank_flag is not None else ""
        return super().to_text_value(text_field, value_subset)

    pack_type = PackType.TITLE_TIMECODE

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


# Title binary group
# SMPTE 306M-2002 Section 9.2.2 Binary group pack (BG)
# IEC 61834-4:1998 4.5 Binary Group (TITLE)
# Also see SMPTE 12M
@dataclass(frozen=True, kw_only=True)
class TitleBinaryGroup(GenericBinaryGroup):
    pack_type = PackType.TITLE_BINARY_GROUP


# AAUX recording date
# IEC 61834-4:1998 8.3 Rec Date (AAUX)
@dataclass(frozen=True, kw_only=True)
class AAUXRecordingDate(GenericDate):
    pack_type = PackType.AAUX_RECORDING_DATE


# AAUX recording time
# IEC 61834-4:1998 8.4 Rec Time (AAUX)
# Also see SMPTE 12M
@dataclass(frozen=True, kw_only=True)
class AAUXRecordingTime(GenericTimecode):
    _time_required = False
    _frames_required = False

    pack_type = PackType.AAUX_RECORDING_TIME


# AAUX binary group
# IEC 61834-4:1998 8.5 Binary Group (AAUX)
@dataclass(frozen=True, kw_only=True)
class AAUXBinaryGroup(GenericBinaryGroup):
    pack_type = PackType.AAUX_BINARY_GROUP


# VAUX recording date
# IEC 61834-4:1998 9.3 Rec Date (Recording date) (VAUX)
@dataclass(frozen=True, kw_only=True)
class VAUXRecordingDate(GenericDate):
    pack_type = PackType.VAUX_RECORDING_DATE


# VAUX recording time
# IEC 61834-4:1998 9.4 Rec Time (VAUX)
# Also see SMPTE 12M
@dataclass(frozen=True, kw_only=True)
class VAUXRecordingTime(GenericTimecode):
    _time_required = False
    _frames_required = False

    pack_type = PackType.VAUX_RECORDING_TIME


# VAUX binary group
# IEC 61834-4:1998 9.5 Binary Group (VAUX)
@dataclass(frozen=True, kw_only=True)
class VAUXBinaryGroup(GenericBinaryGroup):
    pack_type = PackType.VAUX_BINARY_GROUP


# No Info block
# IEC 61834-4:1998 12.16 No Info: No information (SOFT MODE)
# Also, very commonly a dropout - especially in the subcode DIF block
@dataclass(frozen=True, kw_only=True)
class NoInfo(Pack):
    text_fields: ClassVar[CSVFieldMap] = {}

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        assert False

    pack_type = PackType.NO_INFO

    @classmethod
    def _do_parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> NoInfo | None:
        # The standard says that pack_bytes will always be 0xFFFFFFFFFF.  In practice, you'll also
        # "get" this pack as a result of dropouts from other packs: if the leading pack header is
        # lost and becomes 0xFF (this pack type), but the rest of the pack is not lost, then we'd
        # see other non-0xFF bytes here.  Unfortunately, in such a scenario, since the pack header
        # was lost, we don't know what pack that data is supposed to go with.  So we'll just let
        # this pack discard those bytes as it's probably not worth trying to preserve them.
        return cls()

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        return bytes([self.pack_type, 0xFF, 0xFF, 0xFF, 0xFF])


# Unknown pack: holds the bytes for any pack type we don't know about in a particular DIF block.
# These are not aggregated or written to the CSV, since it isn't known if it's meaningful to do
# that.  They do show up when parsing DIF blocks so that we can retain the bytes.
@dataclass(frozen=True, kw_only=True)
class Unknown(Pack):
    # this will always be 5 bytes: includes the pack header
    value: bytes | None = None

    text_fields: ClassVar[CSVFieldMap] = {}

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if self.value is None:
            return "A pack value was not provided."
        if len(self.value) != 5:
            return (
                "The pack value has the wrong length: expected 5 bytes "
                f"but got {len(self.value)}."
            )
        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        assert False

    @classmethod
    def _do_parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> Unknown | None:
        return cls(value=bytes(pack_bytes))

    @classmethod
    def parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> Pack | None:
        assert len(pack_bytes) == 5
        pack = cls._do_parse_binary(pack_bytes, system)
        return pack if pack is not None and pack.validate(system) is None else None

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.value is not None
        return self.value

    def to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        validation_message = self.validate(system)
        if validation_message is not None:
            raise PackValidationError(validation_message)
        b = self._do_to_binary(system)
        assert len(b) == 5
        return b
