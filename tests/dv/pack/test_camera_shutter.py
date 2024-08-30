"""Test packs that store camera shutter data."""

import pytest

import tests.dv.pack.test_base as test_base
import video_tools.dv.pack as pack
from tests.dv.pack.test_base import (
    PackBinaryTestCase,
    PackTextSuccessTestCase,
    PackValidateCase,
)


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic success: consumer",
            "7F FF FF 9D 80",  # from my Sony DCR-TRV460
            pack.CameraShutter(
                shutter_speed_consumer=0x009D,
                shutter_speed_professional_upper_line=None,
                shutter_speed_professional_lower_line=None,
            ),
        ),
        # Additional contrived/synthetic test cases:
        PackBinaryTestCase(
            "basic success: professional",
            "7F 53 35 FF FF",
            pack.CameraShutter(
                shutter_speed_consumer=None,
                shutter_speed_professional_upper_line=0x53,
                shutter_speed_professional_lower_line=0x35,
            ),
        ),
        PackBinaryTestCase(
            "maximum values",
            "7F FE FE FE FF",
            pack.CameraShutter(
                shutter_speed_consumer=0x7FFE,
                shutter_speed_professional_upper_line=0xFE,
                shutter_speed_professional_lower_line=0xFE,
            ),
        ),
        PackBinaryTestCase(
            "minimum values",
            "7F 00 00 01 80",
            pack.CameraShutter(
                shutter_speed_consumer=1,
                shutter_speed_professional_upper_line=0,
                shutter_speed_professional_lower_line=0,
            ),
        ),
        # Some invalid values
        PackBinaryTestCase("invalid reserved bits", "7F FF FF FF 7F", None),
    ],
    ids=lambda tc: tc.name,
)
def test_camera_shutter_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase(
            "consumer camera shutter too low",
            pack.CameraShutter(shutter_speed_consumer=-1),
            "Consumer shutter speed is out of range.",
        ),
        PackValidateCase(
            "consumer camera shutter too high",
            pack.CameraShutter(shutter_speed_consumer=0x8000),
            "Consumer shutter speed is out of range.",
        ),
        PackValidateCase(
            "professional upper line camera shutter too low",
            pack.CameraShutter(shutter_speed_professional_upper_line=-1),
            "Professional upper line shutter speed is out of range.",
        ),
        PackValidateCase(
            "professional upper line camera shutter too high",
            pack.CameraShutter(shutter_speed_professional_upper_line=0xFF),
            "Professional upper line shutter speed is out of range.",
        ),
        PackValidateCase(
            "professional lower line camera shutter too low",
            pack.CameraShutter(shutter_speed_professional_lower_line=-1),
            "Professional lower line shutter speed is out of range.",
        ),
        PackValidateCase(
            "professional lower line camera shutter too high",
            pack.CameraShutter(shutter_speed_professional_lower_line=0xFF),
            "Professional lower line shutter speed is out of range.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_camera_shutter_validate(tc: PackValidateCase) -> None:
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test",
            {
                "shutter_speed_consumer": "8432",
                "shutter_speed_professional_upper_line": "123",
                "shutter_speed_professional_lower_line": "231",
            },
            pack.CameraShutter(
                shutter_speed_consumer=8432,
                shutter_speed_professional_upper_line=123,
                shutter_speed_professional_lower_line=231,
            ),
        ),
        PackTextSuccessTestCase(
            "empty",
            {
                "shutter_speed_consumer": "",
                "shutter_speed_professional_upper_line": "",
                "shutter_speed_professional_lower_line": "",
            },
            pack.CameraShutter(),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_camera_shutter_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.CameraShutter)
