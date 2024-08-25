"""Model classes for working with raw DIF data."""

from __future__ import annotations

import datetime
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, replace
from enum import IntEnum
from typing import Any, ClassVar, NamedTuple, cast

import video_tools.dv.data_util as du
import video_tools.dv.file_info as dv_file_info


# Pack types
# IEC 61834-4:1998
class PackType(IntEnum):
    # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
    # IEC 61834-4:1998 4.4 Time Code (TITLE)
    TITLE_TIME_CODE = 0x13

    # SMPTE 306M-2002 Section 9.2.2 Binary group pack (BG)
    # IEC 61834-4:1998 4.5 Binary Group
    SMPTE_BG = 0x14

    # IEC 61834-4:1998 9.3 Rec Date (Recording date) (VAUX)
    RECORDING_DATE = 0x62

    # IEC 61834-4:1998 9.4 Rec Time (VAUX)
    VAUX_RECORDING_TIME = 0x63

    EMPTY = 0xFF  # All pack bytes are 0xFF (probably a dropout)


# NOTE:  Pack fields are often ultimately all required to be valid, but we allow them to
# be missing during intermediate transformations / in CSV files.  Validity checks are done
# when serializing to/from pack binary blobs.


CSVFieldMap = dict[str | None, type[NamedTuple]]


@dataclass(frozen=True, kw_only=True)
class Pack(ABC):
    @abstractmethod
    def valid(self, system: dv_file_info.DVSystem) -> bool:
        """Indicate whether the contents of the pack are fully valid.

        A fully valid pack can be safely written to a binary DV file.  When reading a binary
        DV file, this function is used to throw out corrupted packs.
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
    def _do_parse_binary(cls, ssyb_bytes: bytes, system: dv_file_info.DVSystem) -> Pack | None:
        """The derived class should parse the bytes into a new Pack object.

        It does not need to assert the length of ssyb_bytes or assert that the pack type is indeed
        correct.  It also does not need to call pack.valid() and return None if it's invalid.  The
        main parse_binary function does those common tasks for you.
        """

    @classmethod
    def parse_binary(cls, ssyb_bytes: bytes, system: dv_file_info.DVSystem) -> Pack | None:
        """Create a new instance of the pack by parsing a binary blob from a DV file.

        The input byte array is expected to be 5 bytes: pack type byte followed by 4 data bytes.
        """
        assert len(ssyb_bytes) == 5
        assert ssyb_bytes[0] == cls.pack_type
        pack = cls._do_parse_binary(ssyb_bytes, system)
        return pack if pack is not None and pack.valid(system) else None

    @abstractmethod
    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        """Convert this pack to binary; the pack can be assumed to be valid."""
        pass

    def to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        """Convert this pack to the 5 byte binary format."""
        assert self.valid(system)
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


smpte_time_pattern = re.compile(
    r"^(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<frame_separator>[:;])(?P<frame>\d{2})$"
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

    def valid(self, system: dv_file_info.DVSystem) -> bool:
        # Main time part must be fully present or fully absent
        time_present = self.hour is not None and self.minute is not None and self.second is not None
        time_absent = self.hour is None and self.minute is None and self.second is None
        if (time_present and time_absent) or (not time_present and not time_absent):
            return False
        # Don't allow specifying frames if there's no other time
        if self.frame is not None and time_absent:
            return False

        # Apply additional requirements based on the derived class
        if self._time_required and time_absent:
            return False
        if time_present and self._frames_required and self.frame is None:
            return False

        # The remaining bits should always be here... physically, the bits are holding _something_
        if (
            self.drop_frame is None
            or self.color_frame is None
            or self.polarity_correction is None
            or self.binary_group_flags is None
        ):
            return False

        # Check ranges of values
        if time_present:
            try:
                # Assertion is to keep mypy happy at this point
                assert self.hour is not None and self.minute is not None and self.second is not None
                datetime.time(hour=self.hour, minute=self.minute, second=self.second)
            except ValueError:
                return False

        if self.frame is not None:
            if self.frame < 0:
                return False
            if system == dv_file_info.DVSystem.SYS_525_60 and self.frame >= 30:
                return False
            if system == dv_file_info.DVSystem.SYS_625_50 and self.frame >= 25:
                return False
            if self.drop_frame and system == dv_file_info.DVSystem.SYS_625_50:
                # drop_frame only applies to NTSC.  But if the frame number is absent completely,
                # we'll skip this verification, since some packs might simply be leaving the bits
                # unconditionally set (who knows? I need to see more test data).
                return False
            assert self.minute is not None and self.second is not None
            if self.drop_frame and self.minute % 10 > 0 and self.second == 0 and self.frame < 2:
                # should have dropped the frame
                return False

        if self.binary_group_flags < 0 or self.binary_group_flags > 0x7:
            return False

        return True

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        match text_field:
            case None:
                match = None
                if text_value:
                    match = smpte_time_pattern.match(text_value)
                    if not match:
                        raise ValueError(f"Parsing error while reading timecode {text_value}.")
                return cls.MainFields(
                    hour=int(match.group("hour")) if match else None,
                    minute=int(match.group("minute")) if match else None,
                    second=int(match.group("second")) if match else None,
                    frame=int(match.group("frame")) if match else None,
                    drop_frame=(match.group("frame_separator") == ";") if match else None,
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
                raise ValueError(f"{text_field} is not a valid field name.")

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        match text_field:
            case None:
                assert isinstance(value_subset, cls.MainFields)
                v = value_subset
                return (
                    (
                        f"{v.hour:02}:{v.minute:02}:{v.second:02};{v.frame:02}"
                        if v.drop_frame
                        else f"{v.hour:02}:{v.minute:02}:{v.second:02}:{v.frame:02}"
                    )
                    if v.hour is not None
                    else ""
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
                raise ValueError(f"{text_field} is not a valid field name.")

    @classmethod
    def _do_parse_binary_generic_tc(
        cls, ssyb_bytes: bytes, system: dv_file_info.DVSystem, **init_kwargs: Any
    ) -> GenericTimecode | None:
        # Good starting points to look at:
        # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
        # IEC 61834-4:1998 4.4 Time Code (TITLE)
        # IEC 61834-4:1998 9.4 Rec Time (VAUX)
        # Also see SMPTE 12M

        # Unpack fields from bytes and validate them.  Validation failures are
        # common due to tape dropouts.

        cf = (ssyb_bytes[1] & 0x80) >> 7
        df = (ssyb_bytes[1] & 0x40) >> 6
        frame_tens = None
        frame_units = None
        if ssyb_bytes[1] & 0x3F != 0x3F:
            frame_tens = (ssyb_bytes[1] & 0x30) >> 4
            if frame_tens > 2:
                return None
            frame_units = ssyb_bytes[1] & 0x0F
            if frame_units > 9:
                return None

        if system == dv_file_info.DVSystem.SYS_525_60:
            pc = (ssyb_bytes[2] & 0x80) >> 7
        elif system == dv_file_info.DVSystem.SYS_625_50:
            bgf0 = (ssyb_bytes[2] & 0x80) >> 7
        second_tens = None
        second_units = None
        if ssyb_bytes[2] & 0x7F != 0x7F:
            second_tens = (ssyb_bytes[2] & 0x70) >> 4
            if second_tens > 5:
                return None
            second_units = ssyb_bytes[2] & 0x0F
            if second_units > 9:
                return None

        if system == dv_file_info.DVSystem.SYS_525_60:
            bgf0 = (ssyb_bytes[3] & 0x80) >> 7
        elif system == dv_file_info.DVSystem.SYS_625_50:
            bgf2 = (ssyb_bytes[3] & 0x80) >> 7
        minute_tens = None
        minute_units = None
        if ssyb_bytes[3] & 0x7F != 0x7F:
            minute_tens = (ssyb_bytes[3] & 0x70) >> 4
            if minute_tens > 5:
                return None
            minute_units = ssyb_bytes[3] & 0x0F
            if minute_units > 9:
                return None

        if system == dv_file_info.DVSystem.SYS_525_60:
            bgf2 = (ssyb_bytes[4] & 0x80) >> 7
        elif system == dv_file_info.DVSystem.SYS_625_50:
            pc = (ssyb_bytes[4] & 0x80) >> 7
        bgf1 = (ssyb_bytes[4] & 0x40) >> 6
        hour_tens = None
        hour_units = None
        if ssyb_bytes[4] & 0x3F != 0x3F:
            hour_tens = (ssyb_bytes[4] & 0x30) >> 4
            if hour_tens > 2:
                return None
            hour_units = ssyb_bytes[4] & 0x0F
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
            drop_frame=df == 1,
            color_frame=(ColorFrame.SYNCHRONIZED if cf == 1 else ColorFrame.UNSYNCHRONIZED),
            polarity_correction=(PolarityCorrection.ODD if pc == 1 else PolarityCorrection.EVEN),
            binary_group_flags=(bgf2 << 2) | (bgf1 << 1) | bgf0,
            **init_kwargs,
        )

    @classmethod
    def _do_parse_binary(
        cls, ssyb_bytes: bytes, system: dv_file_info.DVSystem
    ) -> GenericTimecode | None:
        return cls._do_parse_binary_generic_tc(ssyb_bytes, system)

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        # Good starting points to look at:
        # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
        # IEC 61834-4:1998 4.4 Time Code (TITLE)
        # IEC 61834-4:1998 9.4 Rec Time (VAUX)
        # Also see SMPTE 12M
        assert (  # assertion repeated from valid() to keep mypy happy
            self.drop_frame is not None
            and self.color_frame is not None
            and self.polarity_correction is not None
            and self.binary_group_flags is not None
        )
        ssyb_bytes = [
            self.pack_type,
            (
                (int(self.color_frame) << 7)
                | (0x40 if self.drop_frame else 0x00)
                | (
                    (int(self.frame / 10) << 4) | int(self.frame % 10)
                    if self.frame is not None
                    else 0x3F
                )
            ),
            (
                (int(self.second / 10) << 4) | int(self.second % 10)
                if self.second is not None
                else 0x7F
            ),
            (
                (int(self.minute / 10) << 4) | int(self.minute % 10)
                if self.minute is not None
                else 0x7F
            ),
            ((int(self.hour / 10) << 4) | int(self.hour % 10) if self.hour is not None else 0x3F),
        ]
        pc = int(self.polarity_correction)
        bgf0 = self.binary_group_flags & 0x01
        bgf1 = (self.binary_group_flags & 0x02) >> 1
        bgf2 = (self.binary_group_flags & 0x04) >> 2
        if system == dv_file_info.DVSystem.SYS_525_60:
            ssyb_bytes[2] |= pc << 7
            ssyb_bytes[3] |= bgf0 << 7
            ssyb_bytes[4] |= (bgf2 << 7) | (bgf1 << 6)
        elif system == dv_file_info.DVSystem.SYS_625_50:
            ssyb_bytes[2] |= bgf0 << 7
            ssyb_bytes[3] |= bgf2 << 7
            ssyb_bytes[4] |= (pc << 7) | (bgf1 << 6)
        return bytes(ssyb_bytes)

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
        assert (
            h is not None
            and m is not None
            and s is not None
            and f is not None
            and self.drop_frame is not None
        )
        assert not self.drop_frame or system == dv_file_info.DVSystem.SYS_525_60

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

    class BlankFlagFields(NamedTuple):
        blank_flag: BlankFlag | None

    text_fields: ClassVar[CSVFieldMap] = {
        **GenericTimecode.text_fields,
        "blank_flag": BlankFlagFields,
    }

    def valid(self, system: dv_file_info.DVSystem) -> bool:
        if not super().valid(system):
            return False

        # These two fields physically overlap for different use cases.
        assert self.blank_flag is not None and self.color_frame is not None
        if int(self.blank_flag) != int(self.color_frame):
            return False

        return True

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

    pack_type = PackType.TITLE_TIME_CODE

    @classmethod
    def _do_parse_binary(
        cls, ssyb_bytes: bytes, system: dv_file_info.DVSystem
    ) -> TitleTimecode | None:
        # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
        # IEC 61834-4:1998 4.4 Time Code (TITLE)
        # Also see SMPTE 12M

        # NOTE: CF bit is also BF bit in IEC 61834-4 if not
        # recording TITLE BINARY pack.
        bf = (ssyb_bytes[1] & 0x80) >> 7
        return cast(
            TitleTimecode,
            cls._do_parse_binary_generic_tc(
                ssyb_bytes,
                system,
                blank_flag=BlankFlag.CONTINUOUS if bf == 1 else BlankFlag.DISCONTINUOUS,
            ),
        )


# SMPTE binary group
# SMPTE 306M-2002 Section 9.2.2 Binary group pack (BG)
# IEC 61834-4:1998 4.5 Binary Group
# Also see SMPTE 12M
@dataclass(frozen=True, kw_only=True)
class SMPTEBinaryGroup(Pack):
    # this will always be 4 bytes
    value: bytes | None = None

    class MainFields(NamedTuple):
        value: bytes | None  # Formats as 8 hex digits

    text_fields: ClassVar[CSVFieldMap] = {None: MainFields}

    def valid(self, system: dv_file_info.DVSystem) -> bool:
        return self.value is not None and len(self.value) == 4

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

    pack_type = PackType.SMPTE_BG

    @classmethod
    def _do_parse_binary(
        cls, ssyb_bytes: bytes, system: dv_file_info.DVSystem
    ) -> SMPTEBinaryGroup | None:
        return SMPTEBinaryGroup(value=bytes(ssyb_bytes[1:]))

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.value is not None  # assertion repeated from valid() to keep mypy happy
        return bytes(
            [
                self.pack_type,
                self.value[0],
                self.value[1],
                self.value[2],
                self.value[3],
            ]
        )


recording_date_pattern = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$")
time_zone_pattern = re.compile(r"^(?P<hour>\d{2}):(?P<minute>\d{2})$")


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


# Recording date from subcode pack
# IEC 61834-4:1998 9.3 Rec Date (Recording date) (VAUX)
@dataclass(frozen=True, kw_only=True)
class SubcodeRecordingDate(Pack):
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

    def valid(self, system: dv_file_info.DVSystem) -> bool:
        # Date must be fully present or fully absent
        date_present = self.year is not None and self.month is not None and self.day is not None
        date_absent = self.year is None and self.month is None and self.day is None
        if (date_present and date_absent) or (not date_present and not date_absent):
            return False
        # No week if the date is absent
        if date_absent and self.week is not None:
            return False

        if date_present:
            # Assertion is to keep mypy happy at this point
            assert self.year is not None and self.month is not None and self.day is not None
            try:
                datetime.date(year=self.year, month=self.month, day=self.day)
            except ValueError:
                return False
            if self.year >= 2075 or self.year < 1975:
                return False

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
            return False

        if self.time_zone_hours is not None and self.time_zone_hours >= 24:
            return False

        if self.reserved is None:
            return False

        return True

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        match text_field:
            case None:
                match = None
                if text_value:
                    match = recording_date_pattern.match(text_value)
                    if not match:
                        raise ValueError(f"Parsing error while reading date {text_value}.")
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
                    match = time_zone_pattern.match(text_value)
                    if not match:
                        raise ValueError(f"Parsing error while reading time zone {text_value}.")
                    if match.group("minutes") != "30" and match.group("minutes") != 00:
                        raise ValueError("Minutes portion of time zone must be 30 or 00.")
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
                raise ValueError(f"{text_field} is not a valid field name.")

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
                return f"{tzv.time_zone_hours:02}:{00 if not tzv.time_zone_30_minutes else 30}"
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
                raise ValueError(f"{text_field} is not a valid field name.")

    pack_type = PackType.RECORDING_DATE

    @classmethod
    def _do_parse_binary(
        cls, ssyb_bytes: bytes, system: dv_file_info.DVSystem
    ) -> SubcodeRecordingDate | None:
        # The pack can be present, but all fields absent when the recording date is unknown.

        # Unpack fields from bytes and validate them.  Validation failures are
        # common due to tape dropouts.
        ds = None
        tm = None
        tz_tens = None
        tz_units = None
        # Time zone fields are all present or all absent
        if ssyb_bytes[1] & 0x3F != 0x3F:
            ds = (ssyb_bytes[1] & 0x80) >> 7
            tm = (ssyb_bytes[1] & 0x40) >> 7
            tz_tens = (ssyb_bytes[1] & 0x30) >> 4
            if tz_tens > 2:
                return None
            tz_units = ssyb_bytes[1] & 0x0F
            if tz_units > 9:
                return None

        reserved = (ssyb_bytes[2] & 0xC0) >> 6
        day_tens = None
        day_units = None
        if ssyb_bytes[2] & 0x3F != 0x3F:
            day_tens = (ssyb_bytes[2] & 0x30) >> 4
            if day_tens > 3:
                return None
            day_units = ssyb_bytes[2] & 0x0F
            if day_units > 9:
                return None

        week = (ssyb_bytes[3] & 0xE0) >> 5 if ssyb_bytes[3] & 0xE0 != 0xE0 else None
        month_tens = None
        month_units = None
        if ssyb_bytes[3] & 0x1F != 0x1F:
            month_tens = (ssyb_bytes[3] & 0x10) >> 4
            month_units = ssyb_bytes[3] & 0x0F
            if month_units > 9:
                return None

        year_tens = None
        year_units = None
        year_prefix = None
        if ssyb_bytes[4] & 0xFF != 0xFF:
            year_tens = (ssyb_bytes[4] & 0xF0) >> 4
            if year_tens > 9:
                return None
            year_units = ssyb_bytes[4] & 0x0F
            if year_units > 9:
                return None
            year_prefix = 20 if year_tens < 75 else 19

        return cls(
            year=(
                year_prefix * 100 + year_tens * 10 + year_units
                if year_prefix is not None and year_tens is not None and year_units is not None
                else None
            ),
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
            week=Week(week) if week is not None else None,
            time_zone_hours=(
                tz_tens * 10 + tz_units if tz_tens is not None and tz_units is not None else None
            ),
            time_zone_30_minutes=True if tm == 0 else False,
            daylight_saving_time=DaylightSavingTime.DST if ds == 0 else DaylightSavingTime.NORMAL,
            reserved=reserved,
        )

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.reserved is not None  # assertion repeated from valid() to keep mypy happy
        short_year = self.year % 100 if self.year is not None else None
        ssyb_bytes = [
            self.pack_type,
            (
                (0x01 << 7 if self.daylight_saving_time != DaylightSavingTime.DST else 0x00)
                | (0x01 << 6 if not self.time_zone_30_minutes else 0x00)
                | (
                    (int(self.time_zone_hours / 10) << 4) | int(self.time_zone_hours % 10)
                    if self.time_zone_hours is not None
                    else 0x3F
                )
            ),
            (
                (self.reserved << 6)
                | ((int(self.day / 10) << 4) | int(self.day % 10) if self.day is not None else 0x3F)
            ),
            (
                (int(self.week) << 5 if self.week is not None else 0xE0)
                | (
                    (int(self.month / 10) << 4) | int(self.month % 10)
                    if self.month is not None
                    else 0x1F
                )
            ),
            (
                (int(short_year / 10) << 4) | int(short_year % 10)
                if short_year is not None
                else 0xFF
            ),
        ]
        return bytes(ssyb_bytes)


# VAUX recording time
# IEC 61834-4:1998 9.4 Rec Time (VAUX)
# Also see SMPTE 12M
@dataclass(frozen=True, kw_only=True)
class VAUXRecordingTime(GenericTimecode):
    _time_required = False
    _frames_required = False

    pack_type = PackType.VAUX_RECORDING_TIME
