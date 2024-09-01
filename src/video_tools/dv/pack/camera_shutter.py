"""Model classes for working with camera shutter DIF packs."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import ClassVar

import video_tools.dv.file.info as dv_file_info
from video_tools.typing import DataclassInstance

from .base import CSVFieldMap, Pack, Type


# Camera shutter
# IEC 61834-4:1998 10.16 Shutter (CAMERA)
@dataclass(frozen=True, kw_only=True)
class CameraShutter(Pack):
    shutter_speed_consumer: int | None = None
    shutter_speed_professional_upper_line: int | None = None
    shutter_speed_professional_lower_line: int | None = None

    @dataclass(frozen=True, kw_only=True)
    class ShutterSpeedConsumerFields:
        shutter_speed_consumer: int | None

    @dataclass(frozen=True, kw_only=True)
    class ShutterSpeedProfessionalUpperLineFields:
        shutter_speed_professional_upper_line: int | None

    @dataclass(frozen=True, kw_only=True)
    class ShutterSpeedProfessionalLowerLineFields:
        shutter_speed_professional_lower_line: int | None

    text_fields: ClassVar[CSVFieldMap] = {
        "shutter_speed_consumer": ShutterSpeedConsumerFields,
        "shutter_speed_professional_upper_line": ShutterSpeedProfessionalUpperLineFields,
        "shutter_speed_professional_lower_line": ShutterSpeedProfessionalLowerLineFields,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if self.shutter_speed_consumer is not None and (
            self.shutter_speed_consumer < 1 or self.shutter_speed_consumer > 0x7FFE
        ):
            return "Consumer shutter speed is out of range."

        if self.shutter_speed_professional_upper_line is not None and (
            self.shutter_speed_professional_upper_line < 0
            or self.shutter_speed_professional_upper_line > 0xFE
        ):
            return "Professional upper line shutter speed is out of range."
        if self.shutter_speed_professional_lower_line is not None and (
            self.shutter_speed_professional_lower_line < 0
            or self.shutter_speed_professional_lower_line > 0xFE
        ):
            return "Professional lower line shutter speed is out of range."

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> DataclassInstance:
        match text_field:
            case "shutter_speed_consumer":
                return cls.ShutterSpeedConsumerFields(
                    shutter_speed_consumer=int(text_value) if text_value else None
                )
            case "shutter_speed_professional_upper_line":
                return cls.ShutterSpeedProfessionalUpperLineFields(
                    shutter_speed_professional_upper_line=int(text_value) if text_value else None
                )
            case "shutter_speed_professional_lower_line":
                return cls.ShutterSpeedProfessionalLowerLineFields(
                    shutter_speed_professional_lower_line=int(text_value) if text_value else None
                )
            case _:
                assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: DataclassInstance) -> str:
        match text_field:
            case "shutter_speed_consumer":
                assert isinstance(value_subset, cls.ShutterSpeedConsumerFields)
                return (
                    str(value_subset.shutter_speed_consumer)
                    if value_subset.shutter_speed_consumer is not None
                    else ""
                )
            case "shutter_speed_professional_upper_line":
                assert isinstance(value_subset, cls.ShutterSpeedProfessionalUpperLineFields)
                return (
                    str(value_subset.shutter_speed_professional_upper_line)
                    if value_subset.shutter_speed_professional_upper_line is not None
                    else ""
                )
            case "shutter_speed_professional_lower_line":
                assert isinstance(value_subset, cls.ShutterSpeedProfessionalLowerLineFields)
                return (
                    str(value_subset.shutter_speed_professional_lower_line)
                    if value_subset.shutter_speed_professional_lower_line is not None
                    else ""
                )
            case _:
                assert False

    class _BinaryFields(ctypes.BigEndianStructure):
        _pack_ = 1
        _fields_: ClassVar = [
            # PC 1
            ("ssp1", ctypes.c_uint8, 8),
            # PC 2
            ("ssp2", ctypes.c_uint8, 8),
            # PC 3
            ("ssp_consumer_lsb", ctypes.c_uint8, 8),
            # PC 4
            ("one", ctypes.c_uint8, 1),
            ("ssp_consumer_msb", ctypes.c_uint8, 7),
        ]

    pack_type = Type.CAMERA_SHUTTER

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> CameraShutter | None:
        # Unpack fields from bytes.
        bin = cls._BinaryFields.from_buffer_copy(pack_bytes, 1)

        if bin.one != 0x1:
            return None

        ssp_consumer = (bin.ssp_consumer_msb << 8) | bin.ssp_consumer_lsb
        return cls(
            shutter_speed_consumer=ssp_consumer if ssp_consumer != 0x7FFF else None,
            shutter_speed_professional_upper_line=bin.ssp1 if bin.ssp1 != 0xFF else None,
            shutter_speed_professional_lower_line=bin.ssp2 if bin.ssp2 != 0xFF else None,
        )

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        struct = self._BinaryFields(
            # PC 1
            ssp1=(
                self.shutter_speed_professional_upper_line
                if self.shutter_speed_professional_upper_line is not None
                else 0xFF
            ),
            # PC 2
            ssp2=(
                self.shutter_speed_professional_lower_line
                if self.shutter_speed_professional_lower_line is not None
                else 0xFF
            ),
            # PC 3
            ssp_consumer_lsb=(
                self.shutter_speed_consumer & 0x00FF
                if self.shutter_speed_consumer is not None
                else 0xFF
            ),
            # PC 4
            one=1,
            ssp_consumer_msb=(
                self.shutter_speed_consumer >> 8
                if self.shutter_speed_consumer is not None
                else 0x7F
            ),
        )
        return bytes([self.pack_type, *bytes(struct)])
