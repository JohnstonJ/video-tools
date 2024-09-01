"""Model classes for working with VAUX source DIF packs."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from typing import ClassVar

import video_tools.dv.data_util as du
import video_tools.dv.file.info as dv_file_info
from video_tools.typing import DataclassInstance

from .base import CSVFieldMap, Pack, Type


class BlackAndWhiteFlag(IntEnum):
    BLACK_AND_WHITE = 0x0
    COLOR = 0x1


# Refer to ITU-R Report 624-4
class ColorFramesID(IntEnum):
    CLF_COLOR_FRAME_A_OR_1_2_FIELD = 0x0  # 525-60 or 625-50 system
    CLF_COLOR_FRAME_B_OR_3_4_FIELD = 0x1  # 525-60 or 625-50 system
    CLF_5_6_FIELD = 0x2  # 625-50 system
    CLF_7_8_FIELD = 0x3  # 625-50 system


class SourceCode(Enum):
    CAMERA = auto()
    # MUSE is https://en.wikipedia.org/wiki/Multiple_sub-Nyquist_sampling_encoding
    LINE_MUSE = auto()
    LINE = auto()
    CABLE = auto()
    TUNER = auto()
    PRERECORDED_TAPE = auto()


# IEC 61834-4:1998 9.1 Source (VAUX)
# SMPTE 306M-2002 8.9.1 VAUX source pack (VS)
class SourceType(IntEnum):
    STANDARD_DEFINITION_COMPRESSED_CHROMA = 0x00  # 25 mbps rate, 4:1:1 chroma subsampling on NTSC
    RESERVED_1 = 0x01
    ANALOG_HIGH_DEFINITION_1125_1250 = 0x02  # IEC 61834-3 standard
    RESERVED_3 = 0x03
    STANDARD_DEFINITION_MORE_CHROMA = 0x04  # 50 mbps rate, 4:2:2 chroma subsampling in SMPTE 306M
    RESERVED_4 = 0x04
    RESERVED_5 = 0x05
    RESERVED_6 = 0x06
    RESERVED_7 = 0x07
    RESERVED_8 = 0x08
    RESERVED_9 = 0x09
    RESERVED_10 = 0x0A
    RESERVED_11 = 0x0B
    RESERVED_12 = 0x0C
    RESERVED_13 = 0x0D
    RESERVED_14 = 0x0E
    RESERVED_15 = 0x0F
    RESERVED_16 = 0x10
    RESERVED_17 = 0x11
    RESERVED_18 = 0x12
    RESERVED_19 = 0x13
    RESERVED_20 = 0x14
    RESERVED_21 = 0x15
    RESERVED_22 = 0x16
    RESERVED_23 = 0x17
    RESERVED_24 = 0x18
    RESERVED_25 = 0x19
    RESERVED_26 = 0x1A
    RESERVED_27 = 0x1B
    RESERVED_28 = 0x1C
    RESERVED_29 = 0x1D
    RESERVED_30 = 0x1E
    RESERVED_31 = 0x1F


# VAUX source
# IEC 61834-4:1998 9.1 Source (VAUX)
@dataclass(frozen=True, kw_only=True)
class VAUXSource(Pack):
    source_code: SourceCode | None = None
    tv_channel: int | None = None
    # Tuner category is basically the range of spectrum that the channels are taken from
    tuner_category: int | None = None

    source_type: SourceType | None = None
    field_count: int | None = None
    bw_flag: BlackAndWhiteFlag | None = None
    color_frames_id_valid: bool | None = None
    color_frames_id: ColorFramesID | None = None

    @dataclass(frozen=True, kw_only=True)
    class SourceCodeFields:
        source_code: SourceCode | None

    @dataclass(frozen=True, kw_only=True)
    class TVChannelFields:
        tv_channel: int | None

    @dataclass(frozen=True, kw_only=True)
    class TunerCategoryFields:
        tuner_category: int | None

    @dataclass(frozen=True, kw_only=True)
    class SourceTypeFields:
        source_type: SourceType | None

    @dataclass(frozen=True, kw_only=True)
    class FieldCountFields:
        field_count: int | None

    @dataclass(frozen=True, kw_only=True)
    class BWFlagFields:
        bw_flag: BlackAndWhiteFlag | None

    @dataclass(frozen=True, kw_only=True)
    class ColorFramesIDValidFields:
        color_frames_id_valid: bool | None

    @dataclass(frozen=True, kw_only=True)
    class ColorFramesIDFields:
        color_frames_id: ColorFramesID | None

    text_fields: ClassVar[CSVFieldMap] = {
        "source_code": SourceCodeFields,
        "tv_channel": TVChannelFields,
        "tuner_category": TunerCategoryFields,
        "source_type": SourceTypeFields,
        "field_count": FieldCountFields,
        "bw_flag": BWFlagFields,
        "color_frames_id_valid": ColorFramesIDValidFields,
        "color_frames_id": ColorFramesIDFields,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        # Check that TV channel and tuner category are correct for the given source code
        source_code_name = self.source_code.name if self.source_code is not None else "None"
        match self.source_code:
            case (
                SourceCode.CAMERA
                | SourceCode.LINE_MUSE
                | SourceCode.LINE
                | SourceCode.PRERECORDED_TAPE
                | None
            ):
                if self.tv_channel is not None:
                    return f"No TV channel may be provided for source {source_code_name}."
            case SourceCode.CABLE | SourceCode.TUNER:
                # TV channel must be 1 to 999
                if self.tv_channel is None:
                    return f"A TV channel must be provided for source {source_code_name}."
                if self.tv_channel <= 0 or self.tv_channel >= 1000:
                    return f"TV channel is out of range for source {source_code_name}."
            case _:
                assert False

        if self.source_code != SourceCode.TUNER and self.tuner_category is not None:
            return (
                f"A tuner category was provided for source {source_code_name} "
                "that is not a tuner."
            )
        if self.source_code == SourceCode.TUNER and self.tuner_category is None:
            return f"A tuner category was not provided for source {source_code_name}."

        # Other validations
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

        if self.bw_flag is None:
            return "Black and white flag is required."
        if self.color_frames_id_valid is None:
            return "Color frames ID valid is required."
        if self.color_frames_id is None:
            return "Color frames ID is required."

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> DataclassInstance:
        match text_field:
            case "source_code":
                return cls.SourceCodeFields(
                    source_code=SourceCode[text_value] if text_value else None
                )
            case "tv_channel":
                return cls.TVChannelFields(tv_channel=int(text_value) if text_value else None)
            case "tuner_category":
                return cls.TunerCategoryFields(
                    tuner_category=int(text_value, 0) if text_value else None
                )
            case "source_type":
                return cls.SourceTypeFields(
                    source_type=SourceType[text_value] if text_value else None
                )
            case "field_count":
                return cls.FieldCountFields(field_count=int(text_value) if text_value else None)
            case "bw_flag":
                return cls.BWFlagFields(
                    bw_flag=BlackAndWhiteFlag[text_value] if text_value else None
                )
            case "color_frames_id_valid":
                return cls.ColorFramesIDValidFields(
                    color_frames_id_valid=du.parse_bool(text_value) if text_value else None
                )
            case "color_frames_id":
                return cls.ColorFramesIDFields(
                    color_frames_id=ColorFramesID[text_value] if text_value else None
                )
            case _:
                assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: DataclassInstance) -> str:
        match text_field:
            case "source_code":
                assert isinstance(value_subset, cls.SourceCodeFields)
                return value_subset.source_code.name if value_subset.source_code is not None else ""
            case "tv_channel":
                assert isinstance(value_subset, cls.TVChannelFields)
                return str(value_subset.tv_channel) if value_subset.tv_channel is not None else ""
            case "tuner_category":
                assert isinstance(value_subset, cls.TunerCategoryFields)
                return (
                    du.hex_int(value_subset.tuner_category, 2)
                    if value_subset.tuner_category is not None
                    else ""
                )
            case "source_type":
                assert isinstance(value_subset, cls.SourceTypeFields)
                return value_subset.source_type.name if value_subset.source_type is not None else ""
            case "field_count":
                assert isinstance(value_subset, cls.FieldCountFields)
                return str(value_subset.field_count) if value_subset.field_count is not None else ""
            case "bw_flag":
                assert isinstance(value_subset, cls.BWFlagFields)
                return value_subset.bw_flag.name if value_subset.bw_flag is not None else ""
            case "color_frames_id_valid":
                assert isinstance(value_subset, cls.ColorFramesIDValidFields)
                return (
                    str(value_subset.color_frames_id_valid).upper()
                    if value_subset.color_frames_id_valid is not None
                    else ""
                )
            case "color_frames_id":
                assert isinstance(value_subset, cls.ColorFramesIDFields)
                return (
                    value_subset.color_frames_id.name
                    if value_subset.color_frames_id is not None
                    else ""
                )
            case _:
                assert False

    class _BinaryFields(ctypes.BigEndianStructure):
        _pack_ = 1
        _fields_: ClassVar = [
            ("tv_channel_tens", ctypes.c_uint8, 4),
            ("tv_channel_units", ctypes.c_uint8, 4),
            ("bw", ctypes.c_uint8, 1),
            ("en", ctypes.c_uint8, 1),
            ("clf", ctypes.c_uint8, 2),
            ("tv_channel_hundreds", ctypes.c_uint8, 4),
            ("source_code", ctypes.c_uint8, 2),
            ("field_count", ctypes.c_uint8, 1),
            ("stype", ctypes.c_uint8, 5),
            ("tuner_category", ctypes.c_uint8, 8),
        ]

    pack_type = Type.VAUX_SOURCE

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> VAUXSource | None:
        # Unpack fields from bytes and validate them.
        bin = cls._BinaryFields.from_buffer_copy(pack_bytes, 1)

        # Figure out the source code and TV channel, which all go together
        channel_is_e = (
            bin.tv_channel_hundreds == 0xE
            and bin.tv_channel_tens == 0xE
            and bin.tv_channel_units == 0xE
        )
        channel_is_f = (
            bin.tv_channel_hundreds == 0xF
            and bin.tv_channel_tens == 0xF
            and bin.tv_channel_units == 0xF
        )
        source_code: SourceCode | None
        match bin.source_code:
            case 0x00:
                source_code = SourceCode.CAMERA
                # TV channel and tuner category are expected to be 0xF everywhere
                if not channel_is_f:
                    return None
                tv_channel = None
            case 0x01:
                if channel_is_e:
                    source_code = SourceCode.LINE_MUSE
                elif channel_is_f:
                    source_code = SourceCode.LINE
                else:
                    return None
                tv_channel = None
            case 0x02:
                source_code = SourceCode.CABLE
                if (
                    bin.tv_channel_hundreds > 9
                    or bin.tv_channel_tens > 9
                    or bin.tv_channel_units > 9
                ):
                    return None
                tv_channel = (
                    bin.tv_channel_hundreds * 100 + bin.tv_channel_tens * 10 + bin.tv_channel_units
                )
            case 0x03:
                if channel_is_e:
                    source_code = SourceCode.PRERECORDED_TAPE
                    tv_channel = None
                elif channel_is_f:
                    source_code = None
                    tv_channel = None
                else:
                    source_code = SourceCode.TUNER
                    if (
                        bin.tv_channel_hundreds > 9
                        or bin.tv_channel_tens > 9
                        or bin.tv_channel_units > 9
                    ):
                        return None
                    tv_channel = (
                        bin.tv_channel_hundreds * 100
                        + bin.tv_channel_tens * 10
                        + bin.tv_channel_units
                    )
            case _:
                assert False

        # TV tuner category varies depending on the source
        if source_code == SourceCode.TUNER:
            tuner_category = bin.tuner_category
        elif bin.tuner_category != 0xFF:  # should be NO INFO for every other source code
            return None
        else:
            tuner_category = None

        return cls(
            source_code=source_code,
            tv_channel=tv_channel,
            tuner_category=tuner_category,
            source_type=SourceType(bin.stype),
            field_count=50 if bin.field_count == 1 else 60,
            bw_flag=BlackAndWhiteFlag(bin.bw),
            color_frames_id_valid=True if bin.en == 0 else False,
            color_frames_id=ColorFramesID(bin.clf),
        )

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        match self.source_code:
            case SourceCode.CAMERA:
                source_code = 0x0
                tv_channel_hundreds = 0xF
                tv_channel_tens = 0xF
                tv_channel_units = 0xF
            case SourceCode.LINE_MUSE:
                source_code = 0x1
                tv_channel_hundreds = 0xE
                tv_channel_tens = 0xE
                tv_channel_units = 0xE
            case SourceCode.LINE:
                source_code = 0x1
                tv_channel_hundreds = 0xF
                tv_channel_tens = 0xF
                tv_channel_units = 0xF
            case SourceCode.CABLE | SourceCode.TUNER:
                source_code = 0x2 if self.source_code == SourceCode.CABLE else 0x3
                assert self.tv_channel is not None
                tv_channel_hundreds = int(self.tv_channel / 100)
                tv_channel_tens = int(self.tv_channel / 10) % 10
                tv_channel_units = self.tv_channel % 10
            case SourceCode.PRERECORDED_TAPE:
                source_code = 0x3
                tv_channel_hundreds = 0xE
                tv_channel_tens = 0xE
                tv_channel_units = 0xE
            case None:
                source_code = 0x3
                tv_channel_hundreds = 0xF
                tv_channel_tens = 0xF
                tv_channel_units = 0xF
            case _:
                assert False

        assert self.bw_flag is not None
        assert self.color_frames_id is not None
        assert self.source_type is not None
        struct = self._BinaryFields(
            tv_channel_tens=tv_channel_tens,
            tv_channel_units=tv_channel_units,
            bw=int(self.bw_flag),
            en=0 if self.color_frames_id_valid else 1,
            clf=int(self.color_frames_id),
            tv_channel_hundreds=tv_channel_hundreds,
            source_code=source_code,
            field_count=1 if self.field_count == 50 else 0,
            stype=int(self.source_type),
            tuner_category=self.tuner_category if self.tuner_category is not None else 0xFF,
        )
        return bytes([self.pack_type, *bytes(struct)])
