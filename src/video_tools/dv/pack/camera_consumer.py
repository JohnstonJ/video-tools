"""Model classes for working with consumer camera 1 DIF packs."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

import video_tools.dv.data_util as du
import video_tools.dv.file.info as dv_file_info
from video_tools.typing import DataclassInstance

from .base import CSVFieldMap, Pack, Type
from .camera import FocusMode, _focus_position_bits_to_length, _focus_position_length_to_bits

_iris_digits = 1  # number of decimals to round to for the iris


def __calculate_iris_f_numbers() -> dict[int, float | None]:
    iris: dict[int, float | None] = {}
    for bits in range(0x00, 0x3C + 1):
        iris[bits] = round(2 ** (float(bits) / 8.0), _iris_digits)
    iris[0x3D] = 0.0
    iris[0x3E] = 999.9
    iris[0x3F] = None
    return iris


_iris_bits_to_f_number = __calculate_iris_f_numbers()
_iris_f_number_to_bits = {f: b for b, f in _iris_bits_to_f_number.items()}
# Makes sure every calculated iris value is unique - ensures that we didn't round F number
# too much to ambiguity:
assert len(_iris_bits_to_f_number) == len(_iris_f_number_to_bits)

ValidConsumerIrisFNumbers: list[float] = [k for k in _iris_f_number_to_bits.keys() if k is not None]


class AutoExposureMode(IntEnum):
    FULL_AUTOMATIC = 0x0
    GAIN_PRIORITY = 0x1
    SHUTTER_PRIORITY = 0x2
    IRIS_PRIORITY = 0x3
    MANUAL = 0x4
    RESERVED_5 = 0x5
    RESERVED_6 = 0x6
    RESERVED_7 = 0x7
    RESERVED_8 = 0x8
    RESERVED_9 = 0x9
    RESERVED_10 = 0xA
    RESERVED_11 = 0xB
    RESERVED_12 = 0xC
    RESERVED_13 = 0xD
    RESERVED_14 = 0xE


class WhiteBalanceMode(IntEnum):
    AUTOMATIC = 0x0
    HOLD = 0x1
    ONE_PUSH = 0x2
    PRESET = 0x3
    RESERVED_4 = 0x4
    RESERVED_5 = 0x5
    RESERVED_6 = 0x6


class WhiteBalance(IntEnum):
    CANDLE = 0x00
    INCANDESCENT_LAMP = 0x01
    FLUORESCENT_LAMP_LOW_COLOR_TEMPERATURE = 0x02
    FLUORESCENT_LAMP_HIGH_COLOR_TEMPERATURE = 0x03
    SUNLIGHT = 0x04
    CLOUDINESS = 0x05
    OTHERS = 0x06
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


class PanningDirection(IntEnum):
    SAME_DIRECTION_AS_SCANNING = 0x0
    OPPOSITE_DIRECTION_OF_SCANNING = 0x1


def __calculate_focal_lengths() -> dict[int, int | None]:
    focal_length: dict[int, int | None] = {}
    for bits in range(0, 0xFF):
        msb = bits >> 1
        lsb = bits & 0x1
        focal_length[bits] = msb * (10**lsb)
    focal_length[0xFF] = None
    return focal_length


_focal_length_bits_to_millimeters = __calculate_focal_lengths()
_focal_length_millimeters_to_bits = {
    m: b for b, m in reversed(list(_focal_length_bits_to_millimeters.items()))
}
# NOTE: we don't expect that every calculated focus value is unique: there are multiple ways to
# represent zero.  The items list above is reversed so that LSBs are also zero when MSBs are zero.

ValidFocalLengths: list[int] = [
    k for k in _focal_length_millimeters_to_bits.keys() if k is not None
]


_electric_zoom_digits = 1  # number of decimals to round to for the iris


def __calculate_electric_zoom_magnifications() -> dict[int, float | None]:
    electric_zoom_magnification: dict[int, float | None] = {}
    for units in range(0, 8):
        for tenths in range(0, 10):
            electric_zoom_magnification[(units << 4) | tenths] = float(units) + float(tenths) / 10.0
    electric_zoom_magnification[0x7E] = 8.0  # means >= 8.0
    electric_zoom_magnification[0x7F] = None
    return electric_zoom_magnification


_electric_zoom_bits_to_magnification = __calculate_electric_zoom_magnifications()
_electric_zoom_magnification_to_bits = {
    m: b for b, m in _electric_zoom_bits_to_magnification.items()
}
# Makes sure every calculated magnification value is unique
assert len(_electric_zoom_bits_to_magnification) == len(_electric_zoom_magnification_to_bits)

ValidElectricZoomMagnifications: list[float] = [
    k for k in _electric_zoom_magnification_to_bits.keys() if k is not None
]


# Consumer camera 1
# IEC 61834-4:1998 10.1 Consumer camera 1 (CAMERA)
@dataclass(frozen=True, kw_only=True)
class CameraConsumer1(Pack):
    auto_exposure_mode: AutoExposureMode | None = None
    # Iris is F number rounded to exactly 1 decimal places.
    # Special values:
    #  * 0.0 --> under F1.0
    #  * 999.99 --> closed
    iris: float | None = None
    auto_gain_control: int | None = None

    white_balance_mode: WhiteBalanceMode | None = None
    white_balance: WhiteBalance | None = None

    focus_mode: FocusMode | None = None
    focus_position: int | None = None  # length in centimeters

    @dataclass(frozen=True, kw_only=True)
    class AutoExposureModeFields:
        auto_exposure_mode: AutoExposureMode | None

    @dataclass(frozen=True, kw_only=True)
    class IrisFields:
        iris: float | None

    @dataclass(frozen=True, kw_only=True)
    class AutoGainControlFields:
        auto_gain_control: int | None

    @dataclass(frozen=True, kw_only=True)
    class WhiteBalanceModeFields:
        white_balance_mode: WhiteBalanceMode | None

    @dataclass(frozen=True, kw_only=True)
    class WhiteBalanceFields:
        white_balance: WhiteBalance | None

    @dataclass(frozen=True, kw_only=True)
    class FocusModeFields:
        focus_mode: FocusMode | None

    @dataclass(frozen=True, kw_only=True)
    class FocusPositionFields:
        focus_position: int | None

    text_fields: ClassVar[CSVFieldMap] = {
        "auto_exposure_mode": AutoExposureModeFields,
        "iris": IrisFields,
        "auto_gain_control": AutoGainControlFields,
        "white_balance_mode": WhiteBalanceModeFields,
        "white_balance": WhiteBalanceFields,
        "focus_mode": FocusModeFields,
        "focus_position": FocusPositionFields,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if self.iris is not None and round(self.iris, _iris_digits) not in _iris_f_number_to_bits:
            return "Unsupported iris value selected.  Only certain numbers are allowed."
        if self.auto_gain_control is not None and (
            self.auto_gain_control < 0 or self.auto_gain_control > 0xE
        ):
            return "Auto gain control is out of range."

        if self.focus_mode is None:
            return "Focus mode is required."
        if (
            self.focus_position is not None
            and self.focus_position not in _focus_position_length_to_bits
        ):
            return "Unsupported focus position value selected.  Only certain numbers are allowed."

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> DataclassInstance:
        match text_field:
            case "auto_exposure_mode":
                return cls.AutoExposureModeFields(
                    auto_exposure_mode=AutoExposureMode[text_value] if text_value else None
                )
            case "iris":
                return cls.IrisFields(iris=float(text_value) if text_value else None)
            case "auto_gain_control":
                return cls.AutoGainControlFields(
                    auto_gain_control=int(text_value) if text_value else None
                )
            case "white_balance_mode":
                return cls.WhiteBalanceModeFields(
                    white_balance_mode=WhiteBalanceMode[text_value] if text_value else None
                )
            case "white_balance":
                return cls.WhiteBalanceFields(
                    white_balance=WhiteBalance[text_value] if text_value else None
                )
            case "focus_mode":
                return cls.FocusModeFields(focus_mode=FocusMode[text_value] if text_value else None)
            case "focus_position":
                return cls.FocusPositionFields(
                    focus_position=int(text_value) if text_value else None
                )
            case _:
                assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: DataclassInstance) -> str:
        match text_field:
            case "auto_exposure_mode":
                assert isinstance(value_subset, cls.AutoExposureModeFields)
                return (
                    value_subset.auto_exposure_mode.name
                    if value_subset.auto_exposure_mode is not None
                    else ""
                )
            case "iris":
                assert isinstance(value_subset, cls.IrisFields)
                return str(value_subset.iris) if value_subset.iris is not None else ""
            case "auto_gain_control":
                assert isinstance(value_subset, cls.AutoGainControlFields)
                return (
                    str(value_subset.auto_gain_control)
                    if value_subset.auto_gain_control is not None
                    else ""
                )
            case "white_balance_mode":
                assert isinstance(value_subset, cls.WhiteBalanceModeFields)
                return (
                    value_subset.white_balance_mode.name
                    if value_subset.white_balance_mode is not None
                    else ""
                )
            case "white_balance":
                assert isinstance(value_subset, cls.WhiteBalanceFields)
                return (
                    value_subset.white_balance.name
                    if value_subset.white_balance is not None
                    else ""
                )
            case "focus_mode":
                assert isinstance(value_subset, cls.FocusModeFields)
                return value_subset.focus_mode.name if value_subset.focus_mode is not None else ""
            case "focus_position":
                assert isinstance(value_subset, cls.FocusPositionFields)
                return (
                    str(value_subset.focus_position)
                    if value_subset.focus_position is not None
                    else ""
                )
            case _:
                assert False

    class _BinaryFields(ctypes.BigEndianStructure):
        _pack_ = 1
        _fields_: ClassVar = [
            # PC 1
            ("ones", ctypes.c_uint8, 2),
            ("iris", ctypes.c_uint8, 6),
            # PC 2
            ("ae_mode", ctypes.c_uint8, 4),
            ("agc", ctypes.c_uint8, 4),
            # PC 3
            ("wb_mode", ctypes.c_uint8, 3),
            ("white_balance", ctypes.c_uint8, 5),
            # PC 4
            ("fcm", ctypes.c_uint8, 1),
            ("focus", ctypes.c_uint8, 7),
        ]

    pack_type = Type.CAMERA_CONSUMER_1

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> CameraConsumer1 | None:
        # Unpack fields from bytes.
        bin = cls._BinaryFields.from_buffer_copy(pack_bytes, 1)
        if bin.ones != 0x3:
            return None
        return cls(
            auto_exposure_mode=AutoExposureMode(bin.ae_mode) if bin.ae_mode != 0xF else None,
            iris=_iris_bits_to_f_number[bin.iris],
            auto_gain_control=bin.agc if bin.agc != 0xF else None,
            white_balance_mode=WhiteBalanceMode(bin.wb_mode) if bin.wb_mode != 0x7 else None,
            white_balance=WhiteBalance(bin.white_balance) if bin.white_balance != 0x1F else None,
            focus_mode=FocusMode(bin.fcm),
            focus_position=_focus_position_bits_to_length[bin.focus],
        )

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.focus_mode is not None
        struct = self._BinaryFields(
            # PC 1
            ones=0x3,
            iris=_iris_f_number_to_bits[
                round(self.iris, _iris_digits) if self.iris is not None else None
            ],
            # PC 2
            ae_mode=int(self.auto_exposure_mode) if self.auto_exposure_mode is not None else 0xF,
            agc=self.auto_gain_control if self.auto_gain_control is not None else 0xF,
            # PC 3
            wb_mode=int(self.white_balance_mode) if self.white_balance_mode is not None else 0x7,
            white_balance=int(self.white_balance) if self.white_balance is not None else 0x1F,
            # PC 4
            fcm=int(self.focus_mode),
            focus=_focus_position_length_to_bits[self.focus_position],
        )
        return bytes([self.pack_type, *bytes(struct)])


# Consumer camera 2
# IEC 61834-4:1998 10.2 Consumer camera 2 (CAMERA)
@dataclass(frozen=True, kw_only=True)
class CameraConsumer2(Pack):
    vertical_panning_direction: PanningDirection | None = None
    vertical_panning_speed: int | None = None  # lines per field; 30 means >= 30
    horizontal_panning_direction: PanningDirection | None = None
    horizontal_panning_speed: int | None = None  # pixels per field; 124 means >= 124; must be even

    image_stabilizer_on: bool | None = None

    focal_length: int | None = None  # focal length of lens in mm, as if on a 35 mm film camera lens
    electric_zoom_on: bool | None = None
    electric_zoom_magnification: float | None = None  # magnification factor; 8.0 means >= 8.0

    @dataclass(frozen=True, kw_only=True)
    class VerticalPanningDirectionFields:
        vertical_panning_direction: PanningDirection | None

    @dataclass(frozen=True, kw_only=True)
    class VerticalPanningSpeedFields:
        vertical_panning_speed: int | None

    @dataclass(frozen=True, kw_only=True)
    class HorizontalPanningDirectionFields:
        horizontal_panning_direction: PanningDirection | None

    @dataclass(frozen=True, kw_only=True)
    class HorizontalPanningSpeedFields:
        horizontal_panning_speed: int | None

    @dataclass(frozen=True, kw_only=True)
    class ImageStabilizerOnFields:
        image_stabilizer_on: bool | None

    @dataclass(frozen=True, kw_only=True)
    class FocalLengthFields:
        focal_length: int | None

    @dataclass(frozen=True, kw_only=True)
    class ElectricZoomOnFields:
        electric_zoom_on: bool | None

    @dataclass(frozen=True, kw_only=True)
    class ElectricZoomMagnificationFields:
        electric_zoom_magnification: float | None

    text_fields: ClassVar[CSVFieldMap] = {
        "vertical_panning_direction": VerticalPanningDirectionFields,
        "vertical_panning_speed": VerticalPanningSpeedFields,
        "horizontal_panning_direction": HorizontalPanningDirectionFields,
        "horizontal_panning_speed": HorizontalPanningSpeedFields,
        "image_stabilizer_on": ImageStabilizerOnFields,
        "focal_length": FocalLengthFields,
        "electric_zoom_on": ElectricZoomOnFields,
        "electric_zoom_magnification": ElectricZoomMagnificationFields,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if self.vertical_panning_direction is None:
            return "Vertical panning direction is required."
        if self.vertical_panning_speed is not None and (
            self.vertical_panning_speed < 0 or self.vertical_panning_speed > 0x1E
        ):
            return f"Vertical panning speed is out of range.  Maximum value is {0x1E}."
        if self.horizontal_panning_direction is None:
            return "Horizontal panning direction is required."
        if self.horizontal_panning_speed is not None and (
            self.horizontal_panning_speed < 0 or self.horizontal_panning_speed > 0x3E * 2
        ):
            return f"Horizontal panning speed is out of range.  Maximum value is {0x3E * 2}."
        if self.horizontal_panning_speed is not None and self.horizontal_panning_speed % 2 != 0:
            return "Horizontal panning speed must be an even number."

        if self.image_stabilizer_on is None:
            return "Image stabilizer on value is required."

        if (
            self.focal_length is not None
            and self.focal_length not in _focal_length_millimeters_to_bits
        ):
            return "Unsupported focal length value selected.  Only certain numbers are allowed."
        if self.electric_zoom_on is None:
            return "Electric zoom on value is required."
        if (
            self.electric_zoom_magnification is not None
            and round(self.electric_zoom_magnification, _electric_zoom_digits)
            not in _electric_zoom_magnification_to_bits
        ):
            return "Unsupported electric zoom value selected.  Only certain numbers are allowed."

        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> DataclassInstance:
        match text_field:
            case "vertical_panning_direction":
                return cls.VerticalPanningDirectionFields(
                    vertical_panning_direction=PanningDirection[text_value] if text_value else None
                )
            case "vertical_panning_speed":
                return cls.VerticalPanningSpeedFields(
                    vertical_panning_speed=int(text_value) if text_value else None
                )
            case "horizontal_panning_direction":
                return cls.HorizontalPanningDirectionFields(
                    horizontal_panning_direction=PanningDirection[text_value]
                    if text_value
                    else None
                )
            case "horizontal_panning_speed":
                return cls.HorizontalPanningSpeedFields(
                    horizontal_panning_speed=int(text_value) if text_value else None
                )
            case "image_stabilizer_on":
                return cls.ImageStabilizerOnFields(
                    image_stabilizer_on=du.parse_bool(text_value) if text_value else None
                )
            case "focal_length":
                return cls.FocalLengthFields(focal_length=int(text_value) if text_value else None)
            case "electric_zoom_on":
                return cls.ElectricZoomOnFields(
                    electric_zoom_on=du.parse_bool(text_value) if text_value else None
                )
            case "electric_zoom_magnification":
                return cls.ElectricZoomMagnificationFields(
                    electric_zoom_magnification=float(text_value) if text_value else None
                )
            case _:
                assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: DataclassInstance) -> str:
        match text_field:
            case "vertical_panning_direction":
                assert isinstance(value_subset, cls.VerticalPanningDirectionFields)
                return (
                    value_subset.vertical_panning_direction.name
                    if value_subset.vertical_panning_direction is not None
                    else ""
                )
            case "vertical_panning_speed":
                assert isinstance(value_subset, cls.VerticalPanningSpeedFields)
                return (
                    str(value_subset.vertical_panning_speed)
                    if value_subset.vertical_panning_speed is not None
                    else ""
                )
            case "horizontal_panning_direction":
                assert isinstance(value_subset, cls.HorizontalPanningDirectionFields)
                return (
                    value_subset.horizontal_panning_direction.name
                    if value_subset.horizontal_panning_direction is not None
                    else ""
                )
            case "horizontal_panning_speed":
                assert isinstance(value_subset, cls.HorizontalPanningSpeedFields)
                return (
                    str(value_subset.horizontal_panning_speed)
                    if value_subset.horizontal_panning_speed is not None
                    else ""
                )
            case "image_stabilizer_on":
                assert isinstance(value_subset, cls.ImageStabilizerOnFields)
                return (
                    str(value_subset.image_stabilizer_on).upper()
                    if value_subset.image_stabilizer_on is not None
                    else ""
                )
            case "focal_length":
                assert isinstance(value_subset, cls.FocalLengthFields)
                return (
                    str(value_subset.focal_length) if value_subset.focal_length is not None else ""
                )
            case "electric_zoom_on":
                assert isinstance(value_subset, cls.ElectricZoomOnFields)
                return (
                    str(value_subset.electric_zoom_on).upper()
                    if value_subset.electric_zoom_on is not None
                    else ""
                )
            case "electric_zoom_magnification":
                assert isinstance(value_subset, cls.ElectricZoomMagnificationFields)
                return (
                    str(value_subset.electric_zoom_magnification)
                    if value_subset.electric_zoom_magnification is not None
                    else ""
                )
            case _:
                assert False

    class _BinaryFields(ctypes.BigEndianStructure):
        _pack_ = 1
        _fields_: ClassVar = [
            # PC 1
            ("ones", ctypes.c_uint8, 2),
            ("vpd", ctypes.c_uint8, 1),
            ("v_panning_speed", ctypes.c_uint8, 5),
            # PC 2
            ("is_en", ctypes.c_uint8, 1),
            ("hpd", ctypes.c_uint8, 1),
            ("h_panning_speed", ctypes.c_uint8, 6),
            # PC 3
            ("focal_length", ctypes.c_uint8, 8),
            # PC 4
            ("zen", ctypes.c_uint8, 1),
            ("e_zoom", ctypes.c_uint8, 7),
        ]

    pack_type = Type.CAMERA_CONSUMER_2

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> CameraConsumer2 | None:
        # Unpack fields from bytes.
        bin = cls._BinaryFields.from_buffer_copy(pack_bytes, 1)
        if bin.e_zoom not in _electric_zoom_bits_to_magnification:
            return None
        if bin.ones != 0x3:
            return None
        return cls(
            vertical_panning_direction=PanningDirection(bin.vpd),
            vertical_panning_speed=bin.v_panning_speed if bin.v_panning_speed != 0x1F else None,
            horizontal_panning_direction=PanningDirection(bin.hpd),
            horizontal_panning_speed=(
                bin.h_panning_speed * 2 if bin.h_panning_speed != 0x3F else None
            ),
            image_stabilizer_on=True if bin.is_en == 0 else False,
            focal_length=_focal_length_bits_to_millimeters[bin.focal_length],
            electric_zoom_on=True if bin.zen == 0 else False,
            electric_zoom_magnification=_electric_zoom_bits_to_magnification[bin.e_zoom],
        )

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.vertical_panning_direction is not None
        assert self.horizontal_panning_direction is not None
        struct = self._BinaryFields(
            # PC 1
            ones=0x3,
            vpd=int(self.vertical_panning_direction),
            v_panning_speed=(
                self.vertical_panning_speed if self.vertical_panning_speed is not None else 0x1F
            ),
            # PC 2
            is_en=0 if self.image_stabilizer_on else 1,
            hpd=int(self.horizontal_panning_direction),
            h_panning_speed=(
                self.horizontal_panning_speed >> 1
                if self.horizontal_panning_speed is not None
                else 0x3F
            ),
            # PC 3
            focal_length=_focal_length_millimeters_to_bits[self.focal_length],
            # PC 4
            zen=0 if self.electric_zoom_on else 1,
            e_zoom=_electric_zoom_magnification_to_bits[
                round(self.electric_zoom_magnification, _electric_zoom_digits)
                if self.electric_zoom_magnification is not None
                else None
            ],
        )
        return bytes([self.pack_type, *bytes(struct)])
