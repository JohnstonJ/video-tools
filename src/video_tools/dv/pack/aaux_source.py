"""Model classes for working with AAUX source DIF packs."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, NamedTuple

import video_tools.dv.data_util as du
import video_tools.dv.file.info as dv_file_info

from .base import CSVFieldMap, Pack, Type
from .vaux_source import SourceType


# Locking condition of audio sampling frequency with video signal
class LockedMode(IntEnum):
    LOCKED = 0x0
    UNLOCKED = 0x1


class StereoMode(IntEnum):
    MULTI_STEREO_AUDIO = 0x0
    LUMPED_AUDIO = 0x1


# Whether the audio in CH1 (CH3) is related to audio in CH2 (CH4)
class AudioBlockPairing(IntEnum):
    PAIRED = 0x0
    INDEPENDENT = 0x1


class EmphasisTimeConstant(IntEnum):
    E_50_15 = 0x1  # 50/15 microseconds
    RESERVED = 0x0


class AudioQuantization(IntEnum):
    LINEAR_16_BIT = 0
    NONLINEAR_12_BIT = 1
    LINEAR_20_BIT = 2
    RESERVED_3 = 3
    RESERVED_4 = 4
    RESERVED_5 = 5
    RESERVED_6 = 6
    RESERVED_7 = 7


# AAUX source
# IEC 61834-4:1998 8.1 Source (AAUX)
#
# NOTE: The values are only unique within a given audio block channel: i.e. first 5 or 6 DIF blocks
# in a given sequence, or the second half of the DIF blocks in the sequence.
@dataclass(frozen=True, kw_only=True)
class AAUXSource(Pack):
    # Basic audio information for a channel
    sample_frequency: int | None = None
    quantization: AudioQuantization | None = None
    audio_samples_per_frame: int | None = None  # applies to all channels
    locked_mode: LockedMode | None = None

    # Audio channel layout
    stereo_mode: StereoMode | None = None
    # Number of audio channels within an audio block channel.  Example: first 5 or 6 DIF blocks
    # in a sequence is an audio block channel, which could in turn hold 1 or 2 audio channels.
    audio_block_channel_count: int | None = None
    # audio_mode defines the layout of the audio signal channels (what is
    # left/right/center/surround, etc.).  The values are too complex to encapsulate in an enum.
    # See the table in IEC 61834-4:1998 8.1 Source (AAUX).
    audio_mode: int | None = None
    audio_block_pairing: AudioBlockPairing | None = None
    multi_language: bool | None = None

    # Other information
    source_type: SourceType | None = None  # apparently the same as for VAUX source type
    field_count: int | None = None
    emphasis_on: bool | None = None
    emphasis_time_constant: EmphasisTimeConstant | None = None

    class SampleFrequencyFields(NamedTuple):
        sample_frequency: int | None

    class QuantizationFields(NamedTuple):
        quantization: AudioQuantization | None

    class AudioSamplesPerFrameFields(NamedTuple):
        audio_samples_per_frame: int | None  # applies to all channels

    class LockedModeFields(NamedTuple):
        locked_mode: LockedMode | None

    class StereoModeFields(NamedTuple):
        stereo_mode: StereoMode | None

    class AudioBlockChannelCountFields(NamedTuple):
        audio_block_channel_count: int | None

    class AudioModeFields(NamedTuple):
        audio_mode: int | None

    class AudioBlockPairingFields(NamedTuple):
        audio_block_pairing: AudioBlockPairing | None

    class MultiLanguageFields(NamedTuple):
        multi_language: bool | None

    class FieldCountFields(NamedTuple):
        field_count: int | None

    class SourceTypeFields(NamedTuple):
        source_type: SourceType | None

    class EmphasisOnFields(NamedTuple):
        emphasis_on: bool | None

    class EmphasisTimeConstantFields(NamedTuple):
        emphasis_time_constant: EmphasisTimeConstant | None

    text_fields: ClassVar[CSVFieldMap] = {
        "sample_frequency": SampleFrequencyFields,
        "quantization": QuantizationFields,
        "audio_samples_per_frame": AudioSamplesPerFrameFields,
        "locked_mode": LockedModeFields,
        "stereo_mode": StereoModeFields,
        "audio_block_channel_count": AudioBlockChannelCountFields,
        "audio_mode": AudioModeFields,
        "audio_block_pairing": AudioBlockPairingFields,
        "multi_language": MultiLanguageFields,
        "field_count": FieldCountFields,
        "source_type": SourceTypeFields,
        "emphasis_on": EmphasisOnFields,
        "emphasis_time_constant": EmphasisTimeConstantFields,
    }

    __audio_samples_per_frame_ranges: ClassVar[
        dict[dv_file_info.DVSystem, dict[int, tuple[int, int]]]
    ] = {
        dv_file_info.DVSystem.SYS_525_60: {
            32000: (1053, 1080),
            44100: (1452, 1489),
            48000: (1580, 1620),
        },
        dv_file_info.DVSystem.SYS_625_50: {
            32000: (1264, 1296),
            44100: (1742, 1786),
            48000: (1896, 1944),
        },
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        # Check basic audio information
        if self.sample_frequency is None:
            return "Audio sample frequency is required."
        if (
            self.sample_frequency != 32000
            and self.sample_frequency != 44100
            and self.sample_frequency != 48000
        ):
            return f"Audio sample frequency of {self.sample_frequency} is not supported."

        if self.quantization is None:
            return "Audio quantization is required."

        if self.audio_samples_per_frame is None:
            return "Audio samples per frame is required."
        if (
            self.audio_samples_per_frame
            < self.__audio_samples_per_frame_ranges[system][self.sample_frequency][0]
            or self.audio_samples_per_frame
            > self.__audio_samples_per_frame_ranges[system][self.sample_frequency][1]
        ):
            return "Audio samples per frame is out of range."

        if self.locked_mode is None:
            return "Audio locked mode is required."

        # Audio channel layout
        if self.stereo_mode is None:
            return "Stereo mode enumeration value is required."

        if self.audio_block_channel_count is None:
            return "Audio block channel count is required."
        if self.audio_block_channel_count != 1 and self.audio_block_channel_count != 2:
            return "Audio block channel count must be 1 or 2."

        if self.audio_mode is None:
            return "Audio mode is required."
        if self.audio_mode < 0x0 or self.audio_mode > 0xF:
            return "Audio mode is out of range."

        if self.audio_block_pairing is None:
            return "Audio block pairing is required."

        if self.multi_language is None:
            return "Multi-language flag is required."

        # Other information
        if self.source_type is None:
            return "Source type is required."

        if self.field_count is None:
            return "Field count is required."
        match system:
            case dv_file_info.DVSystem.SYS_525_60:
                if self.field_count != 60:
                    return f"Field count must be 60 for system {system.name}."
            case dv_file_info.DVSystem.SYS_625_50:
                if self.field_count != 50:
                    return f"Field count must be 50 for system {system.name}."
            case _:
                assert False

        if self.emphasis_on is None:
            return "Emphasis on is required."

        if self.emphasis_time_constant is None:
            return "Emphasis time constant is required."

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        match text_field:
            case "sample_frequency":
                return cls.SampleFrequencyFields(
                    sample_frequency=int(text_value) if text_value else None
                )
            case "quantization":
                return cls.QuantizationFields(
                    quantization=AudioQuantization[text_value] if text_value else None
                )
            case "audio_samples_per_frame":
                return cls.AudioSamplesPerFrameFields(
                    audio_samples_per_frame=int(text_value) if text_value else None
                )
            case "locked_mode":
                return cls.LockedModeFields(
                    locked_mode=LockedMode[text_value] if text_value else None
                )
            case "stereo_mode":
                return cls.StereoModeFields(
                    stereo_mode=StereoMode[text_value] if text_value else None
                )
            case "audio_block_channel_count":
                return cls.AudioBlockChannelCountFields(
                    audio_block_channel_count=int(text_value) if text_value else None
                )
            case "audio_mode":
                return cls.AudioModeFields(audio_mode=int(text_value, 0) if text_value else None)
            case "audio_block_pairing":
                return cls.AudioBlockPairingFields(
                    audio_block_pairing=AudioBlockPairing[text_value] if text_value else None
                )
            case "multi_language":
                return cls.MultiLanguageFields(
                    multi_language=du.parse_bool(text_value) if text_value else None
                )
            case "source_type":
                return cls.SourceTypeFields(
                    source_type=SourceType[text_value] if text_value else None
                )
            case "field_count":
                return cls.FieldCountFields(field_count=int(text_value) if text_value else None)
            case "emphasis_on":
                return cls.EmphasisOnFields(
                    emphasis_on=du.parse_bool(text_value) if text_value else None
                )
            case "emphasis_time_constant":
                return cls.EmphasisTimeConstantFields(
                    emphasis_time_constant=EmphasisTimeConstant[text_value] if text_value else None
                )
            case _:
                assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        match text_field:
            case "sample_frequency":
                assert isinstance(value_subset, cls.SampleFrequencyFields)
                return (
                    str(value_subset.sample_frequency)
                    if value_subset.sample_frequency is not None
                    else ""
                )
            case "quantization":
                assert isinstance(value_subset, cls.QuantizationFields)
                return (
                    value_subset.quantization.name if value_subset.quantization is not None else ""
                )
            case "audio_samples_per_frame":
                assert isinstance(value_subset, cls.AudioSamplesPerFrameFields)
                return (
                    str(value_subset.audio_samples_per_frame)
                    if value_subset.audio_samples_per_frame is not None
                    else ""
                )
            case "locked_mode":
                assert isinstance(value_subset, cls.LockedModeFields)
                return value_subset.locked_mode.name if value_subset.locked_mode is not None else ""
            case "stereo_mode":
                assert isinstance(value_subset, cls.StereoModeFields)
                return value_subset.stereo_mode.name if value_subset.stereo_mode is not None else ""
            case "audio_block_channel_count":
                assert isinstance(value_subset, cls.AudioBlockChannelCountFields)
                return (
                    str(value_subset.audio_block_channel_count)
                    if value_subset.audio_block_channel_count is not None
                    else ""
                )
            case "audio_mode":
                assert isinstance(value_subset, cls.AudioModeFields)
                return (
                    du.hex_int(value_subset.audio_mode, 1)
                    if value_subset.audio_mode is not None
                    else ""
                )
            case "audio_block_pairing":
                assert isinstance(value_subset, cls.AudioBlockPairingFields)
                return (
                    value_subset.audio_block_pairing.name
                    if value_subset.audio_block_pairing is not None
                    else ""
                )
            case "multi_language":
                assert isinstance(value_subset, cls.MultiLanguageFields)
                return (
                    str(value_subset.multi_language).upper()
                    if value_subset.multi_language is not None
                    else ""
                )
            case "source_type":
                assert isinstance(value_subset, cls.SourceTypeFields)
                return value_subset.source_type.name if value_subset.source_type is not None else ""
            case "field_count":
                assert isinstance(value_subset, cls.FieldCountFields)
                return str(value_subset.field_count) if value_subset.field_count is not None else ""
            case "emphasis_on":
                assert isinstance(value_subset, cls.EmphasisOnFields)
                return (
                    str(value_subset.emphasis_on).upper()
                    if value_subset.emphasis_on is not None
                    else ""
                )
            case "emphasis_time_constant":
                assert isinstance(value_subset, cls.EmphasisTimeConstantFields)
                return (
                    value_subset.emphasis_time_constant.name
                    if value_subset.emphasis_time_constant is not None
                    else ""
                )
            case _:
                assert False

    class _BinaryFields(ctypes.BigEndianStructure):
        _pack_ = 1
        _fields_: ClassVar = [
            # PC 1
            ("lf", ctypes.c_uint8, 1),
            ("one_1", ctypes.c_uint8, 1),
            ("af_size", ctypes.c_uint8, 6),
            # PC 2
            ("sm", ctypes.c_uint8, 1),
            ("chn", ctypes.c_uint8, 2),
            ("pa", ctypes.c_uint8, 1),
            ("audio_mode", ctypes.c_uint8, 4),
            # PC 3
            ("one_2", ctypes.c_uint8, 1),
            ("ml", ctypes.c_uint8, 1),
            ("field_count", ctypes.c_uint8, 1),
            ("stype", ctypes.c_uint8, 5),
            # PC 4
            ("ef", ctypes.c_uint8, 1),
            ("tc", ctypes.c_uint8, 1),
            ("smp", ctypes.c_uint8, 3),
            ("qu", ctypes.c_uint8, 3),
        ]

    pack_type = Type.AAUX_SOURCE

    __smp_to_freq: ClassVar[dict[int, int]] = {
        0x0: 48000,
        0x1: 44100,
        0x2: 32000,
    }
    __freq_to_smp: ClassVar[dict[int, int]] = {
        48000: 0x0,
        44100: 0x1,
        32000: 0x2,
    }

    __chn_to_channel_count: ClassVar[dict[int, int]] = {
        0x0: 1,
        0x1: 2,
    }
    __channel_count_to_chn: ClassVar[dict[int, int]] = {
        1: 0x0,
        2: 0x1,
    }

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> AAUXSource | None:
        # Unpack fields from bytes and validate them.
        bin = cls._BinaryFields.from_buffer_copy(pack_bytes, 1)

        sample_frequency = cls.__smp_to_freq.get(bin.smp)
        if sample_frequency is None:
            return None

        if bin.one_1 != 1 or bin.one_2 != 1:
            return None

        # We rely on validation to throw this pack out if we end up assigning None to some fields,
        # or writing some other invalid things like audio_samples_per_frame out of range.
        return cls(
            sample_frequency=sample_frequency,
            quantization=AudioQuantization(bin.qu) if bin.qu in AudioQuantization else None,
            audio_samples_per_frame=(
                cls.__audio_samples_per_frame_ranges[system][sample_frequency][0] + bin.af_size
            ),
            locked_mode=LockedMode(bin.lf),
            stereo_mode=StereoMode(bin.sm),
            audio_block_channel_count=cls.__chn_to_channel_count.get(bin.chn),
            audio_mode=bin.audio_mode,
            audio_block_pairing=AudioBlockPairing(bin.pa),
            multi_language=True if bin.ml == 0 else False,
            source_type=SourceType(bin.stype),
            field_count=50 if bin.field_count == 1 else 60,
            emphasis_on=True if bin.ef == 0 else False,
            emphasis_time_constant=EmphasisTimeConstant(bin.tc),
        )

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.sample_frequency is not None
        assert self.locked_mode is not None
        assert self.audio_samples_per_frame is not None
        assert self.stereo_mode is not None
        assert self.audio_block_channel_count is not None
        assert self.audio_block_pairing is not None
        assert self.source_type is not None
        assert self.emphasis_time_constant is not None
        assert self.quantization is not None
        struct = self._BinaryFields(
            # PC 1
            lf=int(self.locked_mode),
            one_1=1,
            af_size=(
                self.audio_samples_per_frame
                - self.__audio_samples_per_frame_ranges[system][self.sample_frequency][0]
            ),
            # PC 2
            sm=int(self.stereo_mode),
            chn=self.__channel_count_to_chn[self.audio_block_channel_count],
            pa=int(self.audio_block_pairing),
            audio_mode=self.audio_mode,
            # PC 3
            one_2=1,
            ml=0 if self.multi_language else 1,
            field_count=1 if self.field_count == 50 else 0,
            stype=int(self.source_type),
            # PC 4
            ef=0 if self.emphasis_on else 1,
            tc=int(self.emphasis_time_constant),
            smp=self.__freq_to_smp[self.sample_frequency],
            qu=int(self.quantization),
        )
        return bytes([self.pack_type, *bytes(struct)])
