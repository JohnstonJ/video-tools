"""Model classes for working with raw DIF data."""

import datetime
import itertools
import re
from collections import defaultdict
from dataclasses import dataclass
from enum import IntEnum


# DIF block types.  Values are the three section type bits SCT2..0
class DIFBlockType(IntEnum):
    HEADER = 0x0
    SUBCODE = 0x1
    VAUX = 0x2
    AUDIO = 0x3
    VIDEO = 0x4


DIF_BLOCK_SIZE = 80

# SMPTE 306M-2002 Section 11.2 Data structure
DIF_SEQUENCE_TRANSMISSION_ORDER = list(
    itertools.chain.from_iterable(
        itertools.chain.from_iterable(
            [
                [[DIFBlockType.HEADER]],
                [[DIFBlockType.SUBCODE]] * 2,
                [[DIFBlockType.VAUX]] * 3,
                [[DIFBlockType.AUDIO], [DIFBlockType.VIDEO] * 15] * 9,
            ]
        )
    )
)


def calculate_dif_block_numbers():
    block_count = defaultdict(int)
    block_numbers = []
    for block_index in range(len(DIF_SEQUENCE_TRANSMISSION_ORDER)):
        block_numbers.append(block_count[DIF_SEQUENCE_TRANSMISSION_ORDER[block_index]])
        block_count[DIF_SEQUENCE_TRANSMISSION_ORDER[block_index]] += 1
    return block_numbers


# Every block section type is individually indexed.
DIF_BLOCK_NUMBER = calculate_dif_block_numbers()


# Subcode pack types
class SSYBPackType(IntEnum):
    SMPTE_TC = 0x13  # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
    SMPTE_BG = 0x14  # SMPTE 306M-2002 Section 9.2.2 Binary group pack (BG)
    RECORDING_DATE = 0x62  # Recording date (can't find documentation on this)
    RECORDING_TIME = 0x63  # Recording time (can't find documentation on this)
    RESERVED = 0xFF  # All pack bytes are 0xFF (could also be a dropout)


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


smpte_time_pattern = re.compile(
    r"^(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<frame_separator>[:;])(?P<frame>\d{2})$"
)


# SMPTE time code
# SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
# Also see SMPTE 12M
@dataclass(frozen=True)
class SMPTETimeCode:
    hour: int
    minute: int
    second: int
    frame: int
    drop_frame: bool
    color_frame: ColorFrame
    polarity_correction: PolarityCorrection
    binary_group_flags: int

    # used for validation; not stored directly in the subcode:
    video_frame_dif_sequence_count: int

    def valid(self):
        assert (
            self.video_frame_dif_sequence_count == 10
            or self.video_frame_dif_sequence_count == 12
        )
        if self.hour >= 24 or self.minute >= 60 or self.second >= 60:
            return False
        if self.video_frame_dif_sequence_count == 10 and self.frame >= 30:
            return False
        if self.video_frame_dif_sequence_count == 12 and self.frame >= 25:
            return False
        if self.drop_frame and self.video_frame_dif_sequence_count == 12:
            # drop_frame only applies to NTSC
            return False
        if self.drop_frame and self.minute % 10 > 0 and self.frame < 2:
            # should have dropped the frame
            return False
        return True

    def format_time_str(self):
        return (
            f"{self.hour:02}:{self.minute:02}:{self.second:02};{self.frame:02}"
            if self.drop_frame
            else f"{self.hour:02}:{self.minute:02}:{self.second:02}:{self.frame:02}"
        )

    @classmethod
    def parse_str(
        cls,
        time,
        color_frame,
        polarity_correction,
        binary_group_flags,
        video_frame_dif_sequence_count,
    ):
        if (
            not time
            and not color_frame
            and not polarity_correction
            and not binary_group_flags
        ):
            return None
        match = smpte_time_pattern.match(time)
        if not match:
            raise ValueError("Parsing error while reading SMPTE time code.")
        val = cls(
            hour=int(match.group("hour")),
            minute=int(match.group("minute")),
            second=int(match.group("second")),
            frame=int(match.group("frame")),
            drop_frame=match.group("frame_separator") == ";",
            color_frame=ColorFrame[color_frame],
            polarity_correction=PolarityCorrection[polarity_correction],
            binary_group_flags=int(binary_group_flags, 0),
            video_frame_dif_sequence_count=video_frame_dif_sequence_count,
        )
        if not val.valid():
            raise ValueError("Parsing error while reading SMPTE time code.")
        return val

    @classmethod
    def parse_ssyb_pack(cls, ssyb_bytes, video_frame_dif_sequence_count):
        assert len(ssyb_bytes) == 5
        assert ssyb_bytes[0] == SSYBPackType.SMPTE_TC
        assert (
            video_frame_dif_sequence_count == 10 or video_frame_dif_sequence_count == 12
        )

        # Unpack fields from bytes and validate them.  Validation failures are
        # common due to tape dropouts.
        cf = (ssyb_bytes[1] & 0x80) >> 7
        df = (ssyb_bytes[1] & 0x40) >> 6
        frame_tens = (ssyb_bytes[1] & 0x30) >> 4
        if frame_tens > 2:
            return None
        frame_units = ssyb_bytes[1] & 0x0F
        if frame_units > 9:
            return None

        if video_frame_dif_sequence_count == 10:  # 525/60 system
            pc = (ssyb_bytes[2] & 0x80) >> 7
        elif video_frame_dif_sequence_count == 12:  # 625/50 system
            bgf0 = (ssyb_bytes[2] & 0x80) >> 7
        second_tens = (ssyb_bytes[2] & 0x70) >> 4
        if second_tens > 5:
            return None
        second_units = ssyb_bytes[2] & 0x0F
        if second_units > 9:
            return None

        if video_frame_dif_sequence_count == 10:  # 525/60 system
            bgf0 = (ssyb_bytes[3] & 0x80) >> 7
        elif video_frame_dif_sequence_count == 12:  # 625/50 system
            bgf2 = (ssyb_bytes[3] & 0x80) >> 7
        minute_tens = (ssyb_bytes[3] & 0x70) >> 4
        if minute_tens > 5:
            return None
        minute_units = ssyb_bytes[3] & 0x0F
        if minute_units > 9:
            return None

        if video_frame_dif_sequence_count == 10:  # 525/60 system
            bgf2 = (ssyb_bytes[4] & 0x80) >> 7
        elif video_frame_dif_sequence_count == 12:  # 625/50 system
            pc = (ssyb_bytes[4] & 0x80) >> 7
        bgf1 = (ssyb_bytes[4] & 0x40) >> 6
        hour_tens = (ssyb_bytes[4] & 0x30) >> 4
        if hour_tens > 2:
            return None
        hour_units = ssyb_bytes[4] & 0x0F
        if hour_units > 9:
            return None

        pack = cls(
            hour=hour_tens * 10 + hour_units,
            minute=minute_tens * 10 + minute_units,
            second=second_tens * 10 + second_units,
            frame=frame_tens * 10 + frame_units,
            drop_frame=df == 1,
            color_frame=(
                ColorFrame.SYNCHRONIZED if cf == 1 else ColorFrame.UNSYNCHRONIZED
            ),
            polarity_correction=(
                PolarityCorrection.ODD if pc == 1 else PolarityCorrection.EVEN
            ),
            binary_group_flags=(bgf2 << 2) | (bgf1 << 1) | bgf0,
            video_frame_dif_sequence_count=video_frame_dif_sequence_count,
        )

        return pack if pack.valid() else None


# SMPTE binary group
# SMPTE 306M-2002 Section 9.2.2 Binary group pack (BG)
# Also see SMPTE 12M
@dataclass(frozen=True)
class SMPTEBinaryGroup:
    # this will always be 4 bytes
    value: bytes

    def valid(self):
        return len(self.value) == 4

    @classmethod
    def parse_str(cls, value):
        if not value:
            return None
        val = cls(
            value=bytes.fromhex(value.removeprefix("0x")),
        )
        if not val.valid():
            raise ValueError("Parsing error while reading SMPTE binary group.")
        return val

    @classmethod
    def parse_ssyb_pack(cls, ssyb_bytes):
        assert len(ssyb_bytes) == 5
        assert ssyb_bytes[0] == SSYBPackType.SMPTE_BG
        return SMPTEBinaryGroup(value=bytes(ssyb_bytes[1:]))


recording_date_pattern = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$"
)


# Recording date from subcode pack
# I can't find a reference for this definition.
@dataclass(frozen=True)
class SubcodeRecordingDate:
    # The year field is a regular 4-digit field for ease of use.
    # However, the subcode only encodes a 2-digit year; we use 75 as the Y2K rollover threshold:
    # https://github.com/MediaArea/MediaInfoLib/blob/abdbb218b07f6cc0d4504c863ac5b42ecfab6fc6/Source/MediaInfo/Multiple/File_DvDif_Analysis.cpp#L1225
    year: int | None
    month: int | None
    day: int | None
    # this will always be 4 bytes; the bits that the date came from are masked out.
    reserved: bytes

    def valid(self):
        # Date must be fully present or fully absent
        date_present = (
            self.year is not None and self.month is not None and self.day is not None
        )
        date_absent = self.year is None and self.month is None and self.day is None
        if (date_present and date_absent) or (not date_present and not date_absent):
            return False

        if date_present:
            try:
                datetime.date(year=self.year, month=self.month, day=self.day)
            except ValueError:
                return False
            if self.year >= 2075 or self.year < 1975:
                return False

        if len(self.reserved) != 4:
            return False
        return True

    def format_date_str(self):
        return (
            f"{self.year:02}-{self.month:02}-{self.day:02}"
            if self.valid() and self.year is not None
            else ""
        )

    @classmethod
    def parse_str(cls, date, reserved):
        if not date and not reserved:
            return None
        match = recording_date_pattern.match(date)
        if not match:
            raise ValueError("Parsing error while reading recording date.")
        val = cls(
            year=int(match.group("year")),
            month=int(match.group("month")),
            day=int(match.group("day")),
            reserved=bytes.fromhex(reserved.removeprefix("0x")),
        )
        if not val.valid():
            raise ValueError("Parsing error while reading recording date.")
        return val

    @classmethod
    def parse_ssyb_pack(cls, ssyb_bytes):
        assert len(ssyb_bytes) == 5
        assert ssyb_bytes[0] == SSYBPackType.RECORDING_DATE

        # The pack can be present, but all date fields absent.
        day_tens = None
        day_units = None
        month_tens = None
        month_units = None
        year_tens = None
        year_units = None
        year_prefix = None

        # Unpack fields from bytes and validate them.  Validation failures are
        # common due to tape dropouts.
        if ssyb_bytes[2] & 0x3F != 0x3F:
            day_tens = (ssyb_bytes[2] & 0x30) >> 4
            if day_tens > 3:
                return None
            day_units = ssyb_bytes[2] & 0x0F
            if day_units > 9:
                return None

        if ssyb_bytes[3] & 0x1F != 0x1F:
            month_tens = (ssyb_bytes[3] & 0x10) >> 4
            if month_tens > 1:
                return None
            month_units = ssyb_bytes[3] & 0x0F
            if month_units > 9:
                return None

        if ssyb_bytes[4] & 0xFF != 0xFF:
            year_tens = (ssyb_bytes[4] & 0xF0) >> 4
            if year_tens > 9:
                return None
            year_units = ssyb_bytes[4] & 0x0F
            if year_units > 9:
                return None
            year_prefix = 20 if year_tens < 75 else 19

        reserved_mask = bytes(b"\xFF\xC0\xE0\x00")
        reserved = bytes([b & m for b, m in zip(ssyb_bytes[1:], reserved_mask)])

        pack = cls(
            year=(
                year_prefix * 100 + year_tens * 10 + year_units
                if year_tens is not None
                else None
            ),
            month=month_tens * 10 + month_units if month_tens is not None else None,
            day=day_tens * 10 + day_units if day_tens is not None else None,
            reserved=reserved,
        )

        return pack if pack.valid() else None


recording_time_pattern = re.compile(
    r"^(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(:(?P<frame>\d{2}))?$"
)


# Recording time from subcode pack
# I can't find a reference for this definition.
@dataclass(frozen=True)
class SubcodeRecordingTime:
    hour: int | None
    minute: int | None
    second: int | None
    frame: int | None
    # this will always be 4 bytes; the bits that the time came from are masked out.
    reserved: bytes

    # used for validation; not stored directly in the subcode:
    video_frame_dif_sequence_count: int

    def valid(self):
        # Main time part must be fully present or fully absent
        time_present = (
            self.hour is not None
            and self.minute is not None
            and self.second is not None
        )
        time_absent = self.hour is None and self.minute is None and self.second is None
        if (time_present and time_absent) or (not time_present and not time_absent):
            return False
        # No frame number if the time is absent
        # (but we can have times without frame numbers)
        if time_absent and self.frame is not None:
            return False

        if time_present:
            try:
                datetime.time(hour=self.hour, minute=self.minute, second=self.second)
            except ValueError:
                return False

        assert (
            self.video_frame_dif_sequence_count == 10
            or self.video_frame_dif_sequence_count == 12
        )
        if self.frame is not None:
            if self.video_frame_dif_sequence_count == 10 and self.frame >= 30:
                return False
            if self.video_frame_dif_sequence_count == 12 and self.frame >= 25:
                return False

        return True

    def format_time_str(self):
        if self.valid() and self.hour is not None and self.frame is not None:
            return f"{self.hour:02}:{self.minute:02}:{self.second:02}:{self.frame:02}"
        elif self.valid() and self.hour is not None:
            return f"{self.hour:02}:{self.minute:02}:{self.second:02}"
        return ""

    @classmethod
    def parse_str(cls, time, reserved, video_frame_dif_sequence_count):
        if not time and not reserved:
            return None
        match = recording_time_pattern.match(time)
        if not match:
            raise ValueError("Parsing error while reading recording time.")
        val = cls(
            hour=int(match.group("hour")),
            minute=int(match.group("minute")),
            second=int(match.group("second")),
            frame=(
                int(match.group("frame")) if match.group("frame") is not None else None
            ),
            reserved=bytes.fromhex(reserved.removeprefix("0x")),
            video_frame_dif_sequence_count=video_frame_dif_sequence_count,
        )
        if not val.valid():
            raise ValueError("Parsing error while reading recording time.")
        return val

    @classmethod
    def parse_ssyb_pack(cls, ssyb_bytes, video_frame_dif_sequence_count):
        assert len(ssyb_bytes) == 5
        assert ssyb_bytes[0] == SSYBPackType.RECORDING_TIME

        # The pack can be present, but all date fields absent.
        # Also, some systems record times without frames
        frame_tens = None
        frame_units = None
        second_tens = None
        second_units = None
        minute_tens = None
        minute_units = None
        hour_tens = None
        hour_units = None

        # Unpack fields from bytes and validate them.  Validation failures are
        # common due to tape dropouts.
        if ssyb_bytes[1] & 0x3F != 0x3F:
            frame_tens = (ssyb_bytes[1] & 0x30) >> 4
            if frame_tens > 2:
                return None
            frame_units = ssyb_bytes[1] & 0x0F
            if frame_units > 9:
                return None

        # Timestamps could be entirely absent
        if ssyb_bytes[2] & 0x7F != 0x7F:
            second_tens = (ssyb_bytes[2] & 0x70) >> 4
            if second_tens > 5:
                return None
            second_units = ssyb_bytes[2] & 0x0F
            if second_units > 9:
                return None

        if ssyb_bytes[3] & 0x7F != 0x7F:
            minute_tens = (ssyb_bytes[3] & 0x70) >> 4
            if minute_tens > 5:
                return None
            minute_units = ssyb_bytes[3] & 0x0F
            if minute_units > 9:
                return None

        if ssyb_bytes[4] & 0x3F != 0x3F:
            hour_tens = (ssyb_bytes[4] & 0x30) >> 4
            if hour_tens > 2:
                return None
            hour_units = ssyb_bytes[4] & 0x0F
            if hour_units > 9:
                return None

        reserved_mask = bytes(b"\xC0\x80\x80\xC0")
        reserved = bytes([b & m for b, m in zip(ssyb_bytes[1:], reserved_mask)])

        pack = cls(
            hour=hour_tens * 10 + hour_units if hour_tens is not None else None,
            minute=minute_tens * 10 + minute_units if minute_tens is not None else None,
            second=second_tens * 10 + second_units if second_tens is not None else None,
            frame=frame_tens * 10 + frame_units if frame_tens is not None else None,
            reserved=reserved,
            video_frame_dif_sequence_count=video_frame_dif_sequence_count,
        )

        return pack if pack.valid() else None


@dataclass
class FrameData:
    """Top-level class containing DV frame metadata."""

    # From DIF block headers
    arbitrary_bits: int

    # From header DIF block
    header_track_application_id: int
    header_audio_application_id: int
    header_video_application_id: int
    header_subcode_application_id: int

    # From subcode DIF block
    subcode_track_application_id: int
    subcode_subcode_application_id: int
    # indexed by: channel number, sequence number, SSYB number
    # value is always the pack header (subcode pack type) when reading a DV file.
    # it may be None when writing if we want to leave the pack unmodified.
    subcode_pack_types: list[list[list[int | None]]]
    subcode_smpte_time_code: SMPTETimeCode | None
    subcode_smpte_binary_group: SMPTEBinaryGroup | None
    subcode_recording_date: SubcodeRecordingDate | None
    subcode_recording_time: SubcodeRecordingTime | None
