"""Test packs that store consumer camera data."""

from dataclasses import replace

import pytest

import tests.dv.pack.test_base as test_base
import video_tools.dv.pack as pack
from tests.dv.pack.test_base import (
    PackBinaryTestCase,
    PackTextSuccessTestCase,
    PackValidateCase,
)

# ======================== CONSUMER CAMERA 1 TESTS ========================


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic success",
            "70 C5 07 1F FF",  # from my Sony DCR-TRV460
            pack.CameraConsumer1(
                auto_exposure_mode=pack.AutoExposureMode.FULL_AUTOMATIC,
                iris=1.5,
                auto_gain_control=7,
                white_balance_mode=pack.WhiteBalanceMode.AUTOMATIC,
                white_balance=None,
                focus_mode=pack.FocusMode.MANUAL,
                focus_position=None,
            ),
        ),
        PackBinaryTestCase(
            "basic success, another example",
            "70 DE 01 1F FF",  # from some old Sony camcorder
            pack.CameraConsumer1(
                auto_exposure_mode=pack.AutoExposureMode.FULL_AUTOMATIC,
                iris=13.5,
                auto_gain_control=1,
                white_balance_mode=pack.WhiteBalanceMode.AUTOMATIC,
                white_balance=None,
                focus_mode=pack.FocusMode.MANUAL,
                focus_position=None,
            ),
        ),
        # Additional contrived/synthetic test cases:
        PackBinaryTestCase(
            "all values in range",  # everything's kind of in the middle here
            "70 E5 37 44 56",
            pack.CameraConsumer1(
                auto_exposure_mode=pack.AutoExposureMode.IRIS_PRIORITY,
                iris=24.7,
                auto_gain_control=7,
                white_balance_mode=pack.WhiteBalanceMode.ONE_PUSH,
                white_balance=pack.WhiteBalance.SUNLIGHT,
                focus_mode=pack.FocusMode.AUTOMATIC,
                focus_position=2100,
            ),
        ),
        PackBinaryTestCase(
            "max calculated values",
            "70 FC 3E 44 7E",
            pack.CameraConsumer1(
                auto_exposure_mode=pack.AutoExposureMode.IRIS_PRIORITY,
                iris=181.0,
                auto_gain_control=0xE,
                white_balance_mode=pack.WhiteBalanceMode.ONE_PUSH,
                white_balance=pack.WhiteBalance.SUNLIGHT,
                focus_mode=pack.FocusMode.AUTOMATIC,
                focus_position=3100,
            ),
        ),
        PackBinaryTestCase(
            "wide open iris",
            "70 FD 37 44 7E",
            pack.CameraConsumer1(
                auto_exposure_mode=pack.AutoExposureMode.IRIS_PRIORITY,
                iris=0.0,
                auto_gain_control=7,
                white_balance_mode=pack.WhiteBalanceMode.ONE_PUSH,
                white_balance=pack.WhiteBalance.SUNLIGHT,
                focus_mode=pack.FocusMode.AUTOMATIC,
                focus_position=3100,
            ),
        ),
        PackBinaryTestCase(
            "closed iris",
            "70 FE 37 44 7E",
            pack.CameraConsumer1(
                auto_exposure_mode=pack.AutoExposureMode.IRIS_PRIORITY,
                iris=999.9,
                auto_gain_control=7,
                white_balance_mode=pack.WhiteBalanceMode.ONE_PUSH,
                white_balance=pack.WhiteBalance.SUNLIGHT,
                focus_mode=pack.FocusMode.AUTOMATIC,
                focus_position=3100,
            ),
        ),
        PackBinaryTestCase(
            "all bits set",
            "70 FF FF FF FF",
            pack.CameraConsumer1(
                auto_exposure_mode=None,
                iris=None,
                auto_gain_control=None,
                white_balance_mode=None,
                white_balance=None,
                focus_mode=pack.FocusMode.MANUAL,
                focus_position=None,
            ),
        ),
        PackBinaryTestCase(
            "all bits mostly clear",
            "70 C0 00 00 00",  # keep reserved bits set
            pack.CameraConsumer1(
                auto_exposure_mode=pack.AutoExposureMode.FULL_AUTOMATIC,
                iris=1.0,
                auto_gain_control=0,
                white_balance_mode=pack.WhiteBalanceMode.AUTOMATIC,
                white_balance=pack.WhiteBalance.CANDLE,
                focus_mode=pack.FocusMode.AUTOMATIC,
                focus_position=0,
            ),
        ),
        # Some invalid values
        PackBinaryTestCase("invalid reserved bits", "70 00 00 00 00", None),
    ],
    ids=lambda tc: tc.name,
)
def test_camera_consumer_1_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc)


SIMPLE_CAMERA_CONSUMER_1 = pack.CameraConsumer1(
    auto_exposure_mode=pack.AutoExposureMode.FULL_AUTOMATIC,
    iris=1.5,
    auto_gain_control=7,
    white_balance_mode=pack.WhiteBalanceMode.AUTOMATIC,
    white_balance=None,
    focus_mode=pack.FocusMode.MANUAL,
    focus_position=None,
)


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase(
            "unsupported iris",
            replace(SIMPLE_CAMERA_CONSUMER_1, iris=50.2),
            "Unsupported iris value selected.  Only certain numbers are allowed.",
        ),
        PackValidateCase(
            "auto gain control too low",
            replace(SIMPLE_CAMERA_CONSUMER_1, auto_gain_control=-1),
            "Auto gain control is out of range.",
        ),
        PackValidateCase(
            "auto gain control too high",
            replace(SIMPLE_CAMERA_CONSUMER_1, auto_gain_control=0xF),
            "Auto gain control is out of range.",
        ),
        PackValidateCase(
            "focus mode required",
            replace(SIMPLE_CAMERA_CONSUMER_1, focus_mode=None),
            "Focus mode is required.",
        ),
        PackValidateCase(
            "unsupported focus",
            replace(SIMPLE_CAMERA_CONSUMER_1, focus_position=43),
            "Unsupported focus position value selected.  Only certain numbers are allowed.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_camera_consumer_1_validate(tc: PackValidateCase) -> None:
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test",
            {
                "auto_exposure_mode": "FULL_AUTOMATIC",
                "iris": "1.5",
                "auto_gain_control": "7",
                "white_balance_mode": "AUTOMATIC",
                "white_balance": "CLOUDINESS",
                "focus_mode": "MANUAL",
                "focus_position": "123",
            },
            pack.CameraConsumer1(
                auto_exposure_mode=pack.AutoExposureMode.FULL_AUTOMATIC,
                iris=1.5,
                auto_gain_control=7,
                white_balance_mode=pack.WhiteBalanceMode.AUTOMATIC,
                white_balance=pack.WhiteBalance.CLOUDINESS,
                focus_mode=pack.FocusMode.MANUAL,
                focus_position=123,
            ),
        ),
        PackTextSuccessTestCase(
            "empty",
            {
                "auto_exposure_mode": "",
                "iris": "",
                "auto_gain_control": "",
                "white_balance_mode": "",
                "white_balance": "",
                "focus_mode": "",
                "focus_position": "",
            },
            pack.CameraConsumer1(),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_camera_consumer_1_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.CameraConsumer1)


# ======================== CONSUMER CAMERA 2 TESTS ========================


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic success",
            "71 FF 7F FF FF",  # from my Sony DCR-TRV460
            pack.CameraConsumer2(
                vertical_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                vertical_panning_speed=None,
                horizontal_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                horizontal_panning_speed=None,
                image_stabilizer_on=True,
                focal_length=None,
                electric_zoom_on=False,
                electric_zoom_magnification=None,
            ),
        ),
        # Additional contrived/synthetic test cases:
        PackBinaryTestCase(
            "all values in range",  # everything's kind of in the middle here
            "71 D5 DB B5 57",
            pack.CameraConsumer2(
                vertical_panning_direction=pack.PanningDirection.SAME_DIRECTION_AS_SCANNING,
                vertical_panning_speed=21,
                horizontal_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                horizontal_panning_speed=54,
                image_stabilizer_on=False,
                focal_length=900,
                electric_zoom_on=True,
                electric_zoom_magnification=5.7,
            ),
        ),
        PackBinaryTestCase(
            "max calculated values",
            "71 FE BE FE 79",
            pack.CameraConsumer2(
                vertical_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                vertical_panning_speed=30,
                horizontal_panning_direction=pack.PanningDirection.SAME_DIRECTION_AS_SCANNING,
                horizontal_panning_speed=124,
                image_stabilizer_on=False,
                focal_length=127,
                electric_zoom_on=True,
                electric_zoom_magnification=7.9,
            ),
        ),
        PackBinaryTestCase(
            "max magnification",
            "71 FE BE FE 7E",
            pack.CameraConsumer2(
                vertical_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                vertical_panning_speed=30,
                horizontal_panning_direction=pack.PanningDirection.SAME_DIRECTION_AS_SCANNING,
                horizontal_panning_speed=124,
                image_stabilizer_on=False,
                focal_length=127,
                electric_zoom_on=True,
                electric_zoom_magnification=8.0,
            ),
        ),
        PackBinaryTestCase(
            "all bits set",
            "71 FF FF FF FF",
            pack.CameraConsumer2(
                vertical_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                vertical_panning_speed=None,
                horizontal_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                horizontal_panning_speed=None,
                image_stabilizer_on=False,
                focal_length=None,
                electric_zoom_on=False,
                electric_zoom_magnification=None,
            ),
        ),
        PackBinaryTestCase(
            "all bits mostly clear",
            "71 C0 00 00 00",  # keep reserved bits set
            pack.CameraConsumer2(
                vertical_panning_direction=pack.PanningDirection.SAME_DIRECTION_AS_SCANNING,
                vertical_panning_speed=0,
                horizontal_panning_direction=pack.PanningDirection.SAME_DIRECTION_AS_SCANNING,
                horizontal_panning_speed=0,
                image_stabilizer_on=True,
                focal_length=0,
                electric_zoom_on=True,
                electric_zoom_magnification=0.0,
            ),
        ),
        # Some invalid values
        PackBinaryTestCase("invalid zoom", "71 C0 00 00 5A", None),
        PackBinaryTestCase("invalid reserved bits", "71 00 00 00 00", None),
    ],
    ids=lambda tc: tc.name,
)
def test_camera_consumer_2_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc)


SIMPLE_CAMERA_CONSUMER_2 = pack.CameraConsumer2(
    vertical_panning_direction=pack.PanningDirection.SAME_DIRECTION_AS_SCANNING,
    vertical_panning_speed=21,
    horizontal_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
    horizontal_panning_speed=54,
    image_stabilizer_on=False,
    focal_length=900,
    electric_zoom_on=True,
    electric_zoom_magnification=5.7,
)


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase(
            "vertical panning direction required",
            replace(SIMPLE_CAMERA_CONSUMER_2, vertical_panning_direction=None),
            "Vertical panning direction is required.",
        ),
        PackValidateCase(
            "vertical panning speed too low",
            replace(SIMPLE_CAMERA_CONSUMER_2, vertical_panning_speed=-1),
            "Vertical panning speed is out of range.  Maximum value is 30.",
        ),
        PackValidateCase(
            "vertical panning speed too high",
            replace(SIMPLE_CAMERA_CONSUMER_2, vertical_panning_speed=31),
            "Vertical panning speed is out of range.  Maximum value is 30.",
        ),
        PackValidateCase(
            "horizontal panning direction required",
            replace(SIMPLE_CAMERA_CONSUMER_2, horizontal_panning_direction=None),
            "Horizontal panning direction is required.",
        ),
        PackValidateCase(
            "horizontal panning speed too low",
            replace(SIMPLE_CAMERA_CONSUMER_2, horizontal_panning_speed=-1),
            "Horizontal panning speed is out of range.  Maximum value is 124.",
        ),
        PackValidateCase(
            "horizontal panning speed too high",
            replace(SIMPLE_CAMERA_CONSUMER_2, horizontal_panning_speed=126),
            "Horizontal panning speed is out of range.  Maximum value is 124.",
        ),
        PackValidateCase(
            "horizontal panning speed not even",
            replace(SIMPLE_CAMERA_CONSUMER_2, horizontal_panning_speed=15),
            "Horizontal panning speed must be an even number.",
        ),
        PackValidateCase(
            "image stabilizer on required",
            replace(SIMPLE_CAMERA_CONSUMER_2, image_stabilizer_on=None),
            "Image stabilizer on value is required.",
        ),
        PackValidateCase(
            "unsupported focal length",
            replace(SIMPLE_CAMERA_CONSUMER_2, focal_length=901),
            "Unsupported focal length value selected.  Only certain numbers are allowed.",
        ),
        PackValidateCase(
            "electric zoom on value required",
            replace(SIMPLE_CAMERA_CONSUMER_2, electric_zoom_on=None),
            "Electric zoom on value is required.",
        ),
        PackValidateCase(
            "unsupported electric zoom",
            replace(SIMPLE_CAMERA_CONSUMER_2, electric_zoom_magnification=8.5),
            "Unsupported electric zoom value selected.  Only certain numbers are allowed.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_camera_consumer_2_validate(tc: PackValidateCase) -> None:
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test",
            {
                "vertical_panning_direction": "SAME_DIRECTION_AS_SCANNING",
                "vertical_panning_speed": "21",
                "horizontal_panning_direction": "OPPOSITE_DIRECTION_OF_SCANNING",
                "horizontal_panning_speed": "54",
                "image_stabilizer_on": "FALSE",
                "focal_length": "900",
                "electric_zoom_on": "TRUE",
                "electric_zoom_magnification": "5.7",
            },
            pack.CameraConsumer2(
                vertical_panning_direction=pack.PanningDirection.SAME_DIRECTION_AS_SCANNING,
                vertical_panning_speed=21,
                horizontal_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                horizontal_panning_speed=54,
                image_stabilizer_on=False,
                focal_length=900,
                electric_zoom_on=True,
                electric_zoom_magnification=5.7,
            ),
        ),
        PackTextSuccessTestCase(
            "empty",
            {
                "vertical_panning_direction": "",
                "vertical_panning_speed": "",
                "horizontal_panning_direction": "",
                "horizontal_panning_speed": "",
                "image_stabilizer_on": "",
                "focal_length": "",
                "electric_zoom_on": "",
                "electric_zoom_magnification": "",
            },
            pack.CameraConsumer2(),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_camera_consumer_2_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.CameraConsumer2)
