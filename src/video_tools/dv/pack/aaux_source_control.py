"""Model classes for working with VAUX source control DIF packs."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import IntEnum
from fractions import Fraction
from typing import ClassVar

import video_tools.dv.data_util as du
import video_tools.dv.file.info as dv_file_info
from video_tools.typing import DataclassInstance

from .base import CSVFieldMap, Pack, Type
from .source_control import CompressionCount, CopyProtection, InputSource, SourceSituation


class AAUXRecordingMode(IntEnum):
    ORIGINAL = 0x1
    ONE_CHANNEL_INSERT = 0x3
    TWO_CHANNEL_INSERT = 0x5
    FOUR_CHANNEL_INSERT = 0x4
    INVALID = 0x7


class InsertChannel(IntEnum):
    CHANNEL_1 = 0x0
    CHANNEL_2 = 0x1
    CHANNEL_3 = 0x2
    CHANNEL_4 = 0x3
    CHANNELS_1_2 = 0x4
    CHANNELS_3_4 = 0x5
    CHANNELS_1_2_3_4 = 0x6


class Direction(IntEnum):
    FORWARD = 0x1
    REVERSE = 0x0


def __calculate_playback_speeds() -> dict[int, Fraction | None]:
    speeds: dict[int, Fraction | None] = {}

    # First row of playback speeds (coarse value 0) is special
    speeds[0x00] = Fraction()
    speeds[0x01] = Fraction(1, 32)  # really just means "some speed slower than 1/16"
    for fine_bits in range(0x2, 0xF + 1):
        speeds[fine_bits] = Fraction(1, 18 - fine_bits)

    # Remaining rows of coarse speeds follows some simple exponential rules
    for coarse_bits in range(0x1, 0x7 + 1):
        coarse_value = Fraction(2) ** (-1 + coarse_bits - 1)
        for fine_bits in range(0, 0xF + 1):
            fine_value = Fraction(fine_bits, Fraction(2) ** (6 - coarse_bits))
            # Note that the very final cell value with all bits set means "no information"
            # or "unknown speed"
            speeds[(coarse_bits << 4) | fine_bits] = (
                coarse_value + fine_value if coarse_bits != 0x7 or fine_bits != 0xF else None
            )
    return speeds


_playback_speed_bits_to_fraction = __calculate_playback_speeds()
_playback_speed_fraction_to_bits = {f: b for b, f in _playback_speed_bits_to_fraction.items()}
# Makes sure every calculated fraction is unique:
assert len(_playback_speed_bits_to_fraction) == len(_playback_speed_fraction_to_bits)

ValidPlaybackSpeeds: list[Fraction] = [
    k for k in _playback_speed_fraction_to_bits.keys() if k is not None
]


# AAUX source control
# IEC 61834-4:1998 8.2 Source control (VAUX)
#
# The structure from IEC 61834-4 is actually substantially different from
# SMPTE 306M-2002 7.4.2 AAUX source control pack (ASC), which is yet still different from the draft
# copy of SMPTE 314M I was able to locate.  This structure may need some updates if someone
# reconciles it with a newer/final copy of the SMPTE standards and/or some real-life DV files.
@dataclass(frozen=True, kw_only=True)
class AAUXSourceControl(Pack):
    # Copy protection
    copy_protection: CopyProtection | None = None
    source_situation: SourceSituation | None = None

    # General metadata
    input_source: InputSource | None = None
    compression_count: CompressionCount | None = None
    recording_start_point: bool | None = None
    recording_end_point: bool | None = None
    recording_mode: AAUXRecordingMode | None = None
    insert_channel: InsertChannel | None = None  # only meaningful for Memory in Cassette (MIC)
    genre_category: int | None = None  # massive enumeration of dozens of TV genres

    # Playback information
    direction: Direction | None = None
    # Playback speed works as follows:
    #  - Videotape was recorded from a normal speed source (e.g. camera):
    #    - Tape deck plays back at normal speed during transfer to computer: value is 1
    #    - Tape deck plays at other speed during transfer to computer: value is the alternate speed
    #  - Videotape was recorded from another source that was playing back at a different speed:
    #    - Tape deck plays back at normal speed during transfer to computer: value is the playback
    #      speed from the previous device (i.e. the speed from the previous tape-to-tape transfer)
    #    - Tape deck plays back at other speed during transfer to computer: value is None
    # See IEC 61834-2:1998 Section 11.6 - Playback speed
    # Only specific fractional values are supported.
    playback_speed: Fraction | None = None

    reserved: int | None = None

    @dataclass(frozen=True, kw_only=True)
    class CopyProtectionFields:
        copy_protection: CopyProtection | None

    @dataclass(frozen=True, kw_only=True)
    class SourceSituationFields:
        source_situation: SourceSituation | None

    @dataclass(frozen=True, kw_only=True)
    class InputSourceFields:
        input_source: InputSource | None

    @dataclass(frozen=True, kw_only=True)
    class CompressionCountFields:
        compression_count: CompressionCount | None

    @dataclass(frozen=True, kw_only=True)
    class RecordingStartPointFields:
        recording_start_point: bool | None

    @dataclass(frozen=True, kw_only=True)
    class RecordingEndPointFields:
        recording_end_point: bool | None

    @dataclass(frozen=True, kw_only=True)
    class RecordingModeFields:
        recording_mode: AAUXRecordingMode | None

    @dataclass(frozen=True, kw_only=True)
    class InsertChannelFields:
        insert_channel: InsertChannel | None

    @dataclass(frozen=True, kw_only=True)
    class GenreCategoryFields:
        genre_category: int | None

    @dataclass(frozen=True, kw_only=True)
    class DirectionFields:
        direction: Direction | None

    @dataclass(frozen=True, kw_only=True)
    class PlaybackSpeedFields:
        playback_speed: Fraction | None

    @dataclass(frozen=True, kw_only=True)
    class ReservedFields:
        reserved: int | None

    text_fields: ClassVar[CSVFieldMap] = {
        "copy_protection": CopyProtectionFields,
        "source_situation": SourceSituationFields,
        "input_source": InputSourceFields,
        "compression_count": CompressionCountFields,
        "recording_start_point": RecordingStartPointFields,
        "recording_end_point": RecordingEndPointFields,
        "recording_mode": RecordingModeFields,
        "insert_channel": InsertChannelFields,
        "genre_category": GenreCategoryFields,
        "direction": DirectionFields,
        "playback_speed": PlaybackSpeedFields,
        "reserved": ReservedFields,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if self.copy_protection is None:
            return "Copy protection status is required."

        if self.recording_start_point is None:
            return "Recording start point is required."
        if self.recording_end_point is None:
            return "Recording end point is required."
        if self.recording_mode is None:
            return "Recording mode is required."
        if self.genre_category is None:
            return "Genre category is required."
        if self.genre_category < 0 or self.genre_category > 0x7F:
            return "Genre category is out of range."

        if self.direction is None:
            return "Direction field is required."
        if self.playback_speed not in _playback_speed_fraction_to_bits:
            return "Unsupported playback speed selected.  Only certain fractional values allowed."

        if self.reserved is None:
            return "Reserved field is required."
        if self.reserved < 0 or self.reserved > 0x1:
            return "Reserved field is out of range."

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> DataclassInstance:
        match text_field:
            case "copy_protection":
                return cls.CopyProtectionFields(
                    copy_protection=CopyProtection[text_value] if text_value else None
                )
            case "source_situation":
                return cls.SourceSituationFields(
                    source_situation=SourceSituation[text_value] if text_value else None
                )
            case "input_source":
                return cls.InputSourceFields(
                    input_source=InputSource[text_value] if text_value else None
                )
            case "compression_count":
                return cls.CompressionCountFields(
                    compression_count=CompressionCount[text_value] if text_value else None
                )
            case "recording_start_point":
                return cls.RecordingStartPointFields(
                    recording_start_point=du.parse_bool(text_value) if text_value else None
                )
            case "recording_end_point":
                return cls.RecordingEndPointFields(
                    recording_end_point=du.parse_bool(text_value) if text_value else None
                )
            case "recording_mode":
                return cls.RecordingModeFields(
                    recording_mode=AAUXRecordingMode[text_value] if text_value else None
                )
            case "insert_channel":
                return cls.InsertChannelFields(
                    insert_channel=InsertChannel[text_value] if text_value else None
                )
            case "genre_category":
                return cls.GenreCategoryFields(
                    genre_category=int(text_value, 0) if text_value else None
                )
            case "direction":
                return cls.DirectionFields(direction=Direction[text_value] if text_value else None)
            case "playback_speed":
                return cls.PlaybackSpeedFields(
                    playback_speed=Fraction(text_value) if text_value else None
                )
            case "reserved":
                return cls.ReservedFields(reserved=int(text_value, 0) if text_value else None)
            case _:
                assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: DataclassInstance) -> str:
        match text_field:
            case "copy_protection":
                assert isinstance(value_subset, cls.CopyProtectionFields)
                return (
                    value_subset.copy_protection.name
                    if value_subset.copy_protection is not None
                    else ""
                )
            case "source_situation":
                assert isinstance(value_subset, cls.SourceSituationFields)
                return (
                    value_subset.source_situation.name
                    if value_subset.source_situation is not None
                    else ""
                )
            case "input_source":
                assert isinstance(value_subset, cls.InputSourceFields)
                return (
                    value_subset.input_source.name if value_subset.input_source is not None else ""
                )
            case "compression_count":
                assert isinstance(value_subset, cls.CompressionCountFields)
                return (
                    value_subset.compression_count.name
                    if value_subset.compression_count is not None
                    else ""
                )
            case "recording_start_point":
                assert isinstance(value_subset, cls.RecordingStartPointFields)
                return (
                    str(value_subset.recording_start_point).upper()
                    if value_subset.recording_start_point is not None
                    else ""
                )
            case "recording_end_point":
                assert isinstance(value_subset, cls.RecordingEndPointFields)
                return (
                    str(value_subset.recording_end_point).upper()
                    if value_subset.recording_end_point is not None
                    else ""
                )
            case "recording_mode":
                assert isinstance(value_subset, cls.RecordingModeFields)
                return (
                    value_subset.recording_mode.name
                    if value_subset.recording_mode is not None
                    else ""
                )
            case "insert_channel":
                assert isinstance(value_subset, cls.InsertChannelFields)
                return (
                    value_subset.insert_channel.name
                    if value_subset.insert_channel is not None
                    else ""
                )
            case "genre_category":
                assert isinstance(value_subset, cls.GenreCategoryFields)
                return (
                    du.hex_int(value_subset.genre_category, 2)
                    if value_subset.genre_category is not None
                    else ""
                )
            case "direction":
                assert isinstance(value_subset, cls.DirectionFields)
                return value_subset.direction.name if value_subset.direction is not None else ""
            case "playback_speed":
                assert isinstance(value_subset, cls.PlaybackSpeedFields)
                return (
                    str(value_subset.playback_speed)
                    if value_subset.playback_speed is not None
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
            # PC 1
            ("cgms", ctypes.c_uint8, 2),
            ("isr", ctypes.c_uint8, 2),
            ("cmp", ctypes.c_uint8, 2),
            ("ss", ctypes.c_uint8, 2),
            # PC 2
            ("rec_st", ctypes.c_uint8, 1),
            ("rec_end", ctypes.c_uint8, 1),
            ("rec_mode", ctypes.c_uint8, 3),
            ("insert_ch", ctypes.c_uint8, 3),
            # PC 3
            ("drf", ctypes.c_uint8, 1),
            ("speed", ctypes.c_uint8, 7),
            # PC 4
            ("one", ctypes.c_uint8, 1),
            ("genre_category", ctypes.c_uint8, 7),
        ]

    pack_type = Type.AAUX_SOURCE_CONTROL

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> AAUXSourceControl | None:
        # Unpack fields from bytes.
        bin = cls._BinaryFields.from_buffer_copy(pack_bytes, 1)
        return cls(
            copy_protection=CopyProtection(bin.cgms),
            source_situation=SourceSituation(bin.ss) if bin.ss != 0x3 else None,
            input_source=InputSource(bin.isr) if bin.isr != 0x3 else None,
            compression_count=CompressionCount(bin.cmp) if bin.cmp != 0x3 else None,
            recording_start_point=True if bin.rec_st == 0 else False,
            recording_end_point=True if bin.rec_end == 0 else False,
            recording_mode=(
                AAUXRecordingMode(bin.rec_mode) if bin.rec_mode in AAUXRecordingMode else None
            ),
            insert_channel=InsertChannel(bin.insert_ch) if bin.insert_ch != 0x7 else None,
            genre_category=bin.genre_category,
            direction=Direction(bin.drf),
            playback_speed=_playback_speed_bits_to_fraction[bin.speed],
            reserved=bin.one,
        )

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.copy_protection is not None
        assert self.recording_mode is not None
        assert self.direction is not None
        struct = self._BinaryFields(
            # PC 1
            cgms=int(self.copy_protection),
            isr=int(self.input_source) if self.input_source is not None else 0x3,
            cmp=int(self.compression_count) if self.compression_count is not None else 0x3,
            ss=int(self.source_situation) if self.source_situation is not None else 0x3,
            # PC 2
            rec_st=0 if self.recording_start_point else 1,
            rec_end=0 if self.recording_end_point else 1,
            rec_mode=int(self.recording_mode),
            insert_ch=int(self.insert_channel) if self.insert_channel is not None else 0x7,
            # PC 3
            drf=int(self.direction),
            speed=_playback_speed_fraction_to_bits[self.playback_speed],
            # PC 4
            one=self.reserved,
            genre_category=self.genre_category,
        )
        return bytes([self.pack_type, *bytes(struct)])
