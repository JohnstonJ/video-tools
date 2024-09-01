"""Model classes for working with VAUX source control DIF packs."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

import video_tools.dv.data_util as du
import video_tools.dv.file.info as dv_file_info
from video_tools.typing import DataclassInstance

from .base import CSVFieldMap, Pack, Type
from .source_control import CompressionCount, CopyProtection, InputSource, SourceSituation


class VAUXRecordingMode(IntEnum):
    ORIGINAL = 0x0
    RESERVED = 0x1
    INSERT = 0x2
    INVALID_RECORDING = 0x3


class FrameField(IntEnum):
    ONLY_ONE = 0x0
    BOTH = 0x1


class FrameChange(IntEnum):
    SAME_AS_PREVIOUS = 0x0
    DIFFERENT_FROM_PREVIOUS = 0x1


class StillFieldPicture(IntEnum):
    NO_GAP = 0x0  # no time elapsed between fields in a frame
    TWICE_FRAME_TIME = 0x1  # 1001/60 (NTSC) or 1/50 (PAL/SECAM) seconds elapsed between fields


# VAUX source control
# IEC 61834-4:1998 9.2 Source control (VAUX)
# SMPTE 306M-2002 8.9.2 VAUX source control pack (VSC)
@dataclass(frozen=True, kw_only=True)
class VAUXSourceControl(Pack):
    # Display format / aspect ratio
    broadcast_system: int | None = None  # Type 0 or Type 1, see IEC 61834-4
    display_mode: int | None = None  # See table in IEC 61834-4

    # Frame structure
    frame_field: FrameField | None = None
    first_second: int | None = None  # field number to output first: 1 or 2
    frame_change: FrameChange | None = None
    interlaced: bool | None = None
    still_field_picture: StillFieldPicture | None = None
    still_camera_picture: bool | None = None

    # Copy protection
    copy_protection: CopyProtection | None = None
    source_situation: SourceSituation | None = None

    # General metadata
    input_source: InputSource | None = None
    compression_count: CompressionCount | None = None
    recording_start_point: bool | None = None
    recording_mode: VAUXRecordingMode | None = None
    genre_category: int | None = None  # massive enumeration of dozens of TV genres

    reserved: int | None = None  # [0x0, 0x7] range

    @dataclass(frozen=True, kw_only=True)
    class BroadcastSystemFields:
        broadcast_system: int | None

    @dataclass(frozen=True, kw_only=True)
    class DisplayModeFields:
        display_mode: int | None

    @dataclass(frozen=True, kw_only=True)
    class FrameFieldFields:
        frame_field: FrameField | None

    @dataclass(frozen=True, kw_only=True)
    class FirstSecondFields:
        first_second: int | None

    @dataclass(frozen=True, kw_only=True)
    class FrameChangeFields:
        frame_change: FrameChange | None

    @dataclass(frozen=True, kw_only=True)
    class InterlacedFields:
        interlaced: bool | None

    @dataclass(frozen=True, kw_only=True)
    class StillFieldPictureFields:
        still_field_picture: StillFieldPicture | None

    @dataclass(frozen=True, kw_only=True)
    class StillCameraPictureFields:
        still_camera_picture: bool | None

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
    class RecordingModeFields:
        recording_mode: VAUXRecordingMode | None

    @dataclass(frozen=True, kw_only=True)
    class GenreCategoryFields:
        genre_category: int | None

    @dataclass(frozen=True, kw_only=True)
    class ReservedFields:
        reserved: int | None

    text_fields: ClassVar[CSVFieldMap] = {
        "broadcast_system": BroadcastSystemFields,
        "display_mode": DisplayModeFields,
        "frame_field": FrameFieldFields,
        "first_second": FirstSecondFields,
        "frame_change": FrameChangeFields,
        "interlaced": InterlacedFields,
        "still_field_picture": StillFieldPictureFields,
        "still_camera_picture": StillCameraPictureFields,
        "copy_protection": CopyProtectionFields,
        "source_situation": SourceSituationFields,
        "input_source": InputSourceFields,
        "compression_count": CompressionCountFields,
        "recording_start_point": RecordingStartPointFields,
        "recording_mode": RecordingModeFields,
        "genre_category": GenreCategoryFields,
        "reserved": ReservedFields,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if self.broadcast_system is None:
            return "A broadcast system is required."
        if self.broadcast_system < 0 or self.broadcast_system > 0x3:
            return "Broadcast system is out of range."
        if self.display_mode is None:
            return "A display mode is required."
        if self.display_mode < 0 or self.display_mode > 0x7:
            return "Display mode is out of range."

        if self.frame_field is None:
            return "A frame field is required."
        if self.first_second is None:
            return "A first second value is required."
        if self.first_second < 1 or self.first_second > 2:
            return "The first second value must be 1 or 2 depending on which field is first."
        if self.frame_change is None:
            return "A frame change value is required."
        if self.interlaced is None:
            return "An interlaced field value is required."
        if self.still_field_picture is None:
            return "A still field picture value is required."
        if self.still_camera_picture is None:
            return "A still camera picture value is required."

        if self.copy_protection is None:
            return "Copy protection status is required."

        if self.recording_start_point is None:
            return "Recording start point is required."
        if self.recording_mode is None:
            return "Recording mode is required."
        if self.genre_category is None:
            return "Genre category is required."
        if self.genre_category < 0 or self.genre_category > 0x7F:
            return "Genre category is out of range."

        if self.reserved is None:
            return "Reserved field is required."
        if self.reserved < 0 or self.reserved > 0x7:
            return "Reserved field is out of range."

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> DataclassInstance:
        match text_field:
            case "broadcast_system":
                return cls.BroadcastSystemFields(
                    broadcast_system=int(text_value, 0) if text_value else None
                )
            case "display_mode":
                return cls.DisplayModeFields(
                    display_mode=int(text_value, 0) if text_value else None
                )
            case "frame_field":
                return cls.FrameFieldFields(
                    frame_field=FrameField[text_value] if text_value else None
                )
            case "first_second":
                return cls.FirstSecondFields(first_second=int(text_value) if text_value else None)
            case "frame_change":
                return cls.FrameChangeFields(
                    frame_change=FrameChange[text_value] if text_value else None
                )
            case "interlaced":
                return cls.InterlacedFields(
                    interlaced=du.parse_bool(text_value) if text_value else None
                )
            case "still_field_picture":
                return cls.StillFieldPictureFields(
                    still_field_picture=StillFieldPicture[text_value] if text_value else None
                )
            case "still_camera_picture":
                return cls.StillCameraPictureFields(
                    still_camera_picture=du.parse_bool(text_value) if text_value else None
                )
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
            case "recording_mode":
                return cls.RecordingModeFields(
                    recording_mode=VAUXRecordingMode[text_value] if text_value else None
                )
            case "genre_category":
                return cls.GenreCategoryFields(
                    genre_category=int(text_value, 0) if text_value else None
                )
            case "reserved":
                return cls.ReservedFields(reserved=int(text_value, 0) if text_value else None)
            case _:
                assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: DataclassInstance) -> str:
        match text_field:
            case "broadcast_system":
                assert isinstance(value_subset, cls.BroadcastSystemFields)
                return (
                    du.hex_int(value_subset.broadcast_system, 1)
                    if value_subset.broadcast_system is not None
                    else ""
                )
            case "display_mode":
                assert isinstance(value_subset, cls.DisplayModeFields)
                return (
                    du.hex_int(value_subset.display_mode, 1)
                    if value_subset.display_mode is not None
                    else ""
                )
            case "frame_field":
                assert isinstance(value_subset, cls.FrameFieldFields)
                return value_subset.frame_field.name if value_subset.frame_field is not None else ""
            case "first_second":
                assert isinstance(value_subset, cls.FirstSecondFields)
                return (
                    str(value_subset.first_second) if value_subset.first_second is not None else ""
                )
            case "frame_change":
                assert isinstance(value_subset, cls.FrameChangeFields)
                return (
                    value_subset.frame_change.name if value_subset.frame_change is not None else ""
                )
            case "interlaced":
                assert isinstance(value_subset, cls.InterlacedFields)
                return (
                    str(value_subset.interlaced).upper()
                    if value_subset.interlaced is not None
                    else ""
                )
            case "still_field_picture":
                assert isinstance(value_subset, cls.StillFieldPictureFields)
                return (
                    value_subset.still_field_picture.name
                    if value_subset.still_field_picture is not None
                    else ""
                )
            case "still_camera_picture":
                assert isinstance(value_subset, cls.StillCameraPictureFields)
                return (
                    str(value_subset.still_camera_picture).upper()
                    if value_subset.still_camera_picture is not None
                    else ""
                )
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
            case "recording_mode":
                assert isinstance(value_subset, cls.RecordingModeFields)
                return (
                    value_subset.recording_mode.name
                    if value_subset.recording_mode is not None
                    else ""
                )
            case "genre_category":
                assert isinstance(value_subset, cls.GenreCategoryFields)
                return (
                    du.hex_int(value_subset.genre_category, 2)
                    if value_subset.genre_category is not None
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
            ("one_1", ctypes.c_uint8, 1),
            ("rec_mode", ctypes.c_uint8, 2),
            ("one_2", ctypes.c_uint8, 1),
            ("disp", ctypes.c_uint8, 3),
            # PC 3
            ("ff", ctypes.c_uint8, 1),
            ("fs", ctypes.c_uint8, 1),
            ("fc", ctypes.c_uint8, 1),
            ("il", ctypes.c_uint8, 1),
            ("st", ctypes.c_uint8, 1),
            ("sc", ctypes.c_uint8, 1),
            ("bcsys", ctypes.c_uint8, 2),
            # PC 4
            ("one_3", ctypes.c_uint8, 1),
            ("genre_category", ctypes.c_uint8, 7),
        ]

    pack_type = Type.VAUX_SOURCE_CONTROL

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> VAUXSourceControl | None:
        # Unpack fields from bytes.
        bin = cls._BinaryFields.from_buffer_copy(pack_bytes, 1)

        return cls(
            broadcast_system=bin.bcsys,
            display_mode=bin.disp,
            frame_field=FrameField(bin.ff),
            first_second=2 if bin.fs == 0 else 1,
            frame_change=FrameChange(bin.fc),
            interlaced=True if bin.il == 1 else False,
            still_field_picture=StillFieldPicture(bin.st),
            still_camera_picture=True if bin.sc == 0 else False,
            copy_protection=CopyProtection(bin.cgms),
            source_situation=SourceSituation(bin.ss) if bin.ss != 0x3 else None,
            input_source=InputSource(bin.isr) if bin.isr != 0x3 else None,
            compression_count=CompressionCount(bin.cmp) if bin.cmp != 0x3 else None,
            recording_start_point=True if bin.rec_st == 0 else False,
            recording_mode=VAUXRecordingMode(bin.rec_mode),
            genre_category=bin.genre_category,
            reserved=(bin.one_1 << 2) | (bin.one_2 << 1) | bin.one_3,
        )

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.copy_protection is not None
        assert self.recording_mode is not None
        assert self.frame_field is not None
        assert self.frame_change is not None
        assert self.still_field_picture is not None
        assert self.reserved is not None
        struct = self._BinaryFields(
            # PC 1
            cgms=int(self.copy_protection),
            isr=int(self.input_source) if self.input_source is not None else 0x3,
            cmp=int(self.compression_count) if self.compression_count is not None else 0x3,
            ss=int(self.source_situation) if self.source_situation is not None else 0x3,
            # PC 2
            rec_st=0 if self.recording_start_point else 1,
            one_1=(self.reserved >> 2) & 0x1,
            rec_mode=int(self.recording_mode),
            one_2=(self.reserved >> 1) & 0x1,
            disp=self.display_mode,
            # PC 3
            ff=int(self.frame_field),
            fs=0 if self.first_second == 2 else 1,
            fc=int(self.frame_change),
            il=1 if self.interlaced else 0,
            st=int(self.still_field_picture),
            sc=0 if self.still_camera_picture else 1,
            bcsys=self.broadcast_system,
            # PC 4
            one_3=self.reserved & 0x1,
            genre_category=self.genre_category,
        )
        return bytes([self.pack_type, *bytes(struct)])
