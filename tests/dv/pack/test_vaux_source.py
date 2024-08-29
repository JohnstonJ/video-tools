"""Test packs that store VAUX sources."""

from dataclasses import replace

import pytest

import tests.dv.pack.test_base as test_base
import video_tools.dv.pack as pack
from tests.dv.pack.test_base import (
    NTSC,
    PAL,
    PackBinaryTestCase,
    PackTextSuccessTestCase,
    PackValidateCase,
)


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic success",
            "60 FF FF 00 FF",  # from my Sony DCR-TRV460
            pack.VAUXSource(
                source_code=pack.SourceCode.CAMERA,
                tv_channel=None,
                tuner_category=None,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        PackBinaryTestCase(
            "DVCPRO50",
            "60 FF FF 04 FF",  # from https://archive.org/details/SMPTEColorBarsBadTracking
            pack.VAUXSource(
                source_code=pack.SourceCode.CAMERA,
                tv_channel=None,
                tuner_category=None,
                source_type=pack.SourceType.STANDARD_DEFINITION_MORE_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        # Since the basic cases from the above actual DV files was lacking, contrived test cases:
        #
        # First, we'll go through each SourceCode value
        PackBinaryTestCase(
            "SourceCode CAMERA",
            "60 FF FF 00 FF",
            pack.VAUXSource(
                source_code=pack.SourceCode.CAMERA,
                tv_channel=None,
                tuner_category=None,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        PackBinaryTestCase(
            "SourceCode LINE_MUSE",
            "60 EE FE 40 FF",
            pack.VAUXSource(
                source_code=pack.SourceCode.LINE_MUSE,
                tv_channel=None,
                tuner_category=None,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        PackBinaryTestCase(
            "SourceCode LINE",
            "60 FF FF 40 FF",
            pack.VAUXSource(
                source_code=pack.SourceCode.LINE,
                tv_channel=None,
                tuner_category=None,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        PackBinaryTestCase(
            "SourceCode CABLE",
            "60 36 F4 80 FF",
            pack.VAUXSource(
                source_code=pack.SourceCode.CABLE,
                tv_channel=436,
                tuner_category=None,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        PackBinaryTestCase(
            "SourceCode TUNER",
            "60 36 F4 C0 2B",
            pack.VAUXSource(
                source_code=pack.SourceCode.TUNER,
                tv_channel=436,
                tuner_category=0x2B,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        PackBinaryTestCase(
            "SourceCode PRERECORDED_TAPE",
            "60 EE FE C0 FF",
            pack.VAUXSource(
                source_code=pack.SourceCode.PRERECORDED_TAPE,
                tv_channel=None,
                tuner_category=None,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        PackBinaryTestCase(
            "SourceCode None",
            "60 FF FF C0 FF",
            pack.VAUXSource(
                source_code=None,
                tv_channel=None,
                tuner_category=None,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        # Bounds test the TV channel
        PackBinaryTestCase(
            "channel minimum",
            "60 01 F0 C0 2B",
            pack.VAUXSource(
                source_code=pack.SourceCode.TUNER,
                tv_channel=1,
                tuner_category=0x2B,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        PackBinaryTestCase(
            "channel maximum",
            "60 99 F9 C0 2B",
            pack.VAUXSource(
                source_code=pack.SourceCode.TUNER,
                tv_channel=999,
                tuner_category=0x2B,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                bw_flag=pack.BlackAndWhiteFlag.COLOR,
                color_frames_id_valid=False,
                color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
            ),
        ),
        # Change a bunch of misc fields to different values from what we've been testing
        PackBinaryTestCase(
            "misc weird fields",
            "60 FF 1F EE FF",
            pack.VAUXSource(
                source_code=None,
                tv_channel=None,
                tuner_category=None,
                source_type=pack.SourceType.RESERVED_14,
                field_count=50,
                bw_flag=pack.BlackAndWhiteFlag.BLACK_AND_WHITE,
                color_frames_id_valid=True,
                color_frames_id=pack.ColorFramesID.CLF_COLOR_FRAME_B_OR_3_4_FIELD,
            ),
            system=PAL,
        ),
        # test validations that are in binary parsing, not in validate
        #
        # Try invalid values for each SourceCode
        PackBinaryTestCase("invalid SourceCode CAMERA", "60 EF FF 00 FF", None),  # has channel
        PackBinaryTestCase("invalid SourceCode LINE", "60 EF FF 40 FF", None),  # has channel
        # channels out of range:
        PackBinaryTestCase("invalid SourceCode CABLE", "60 A6 F4 80 FF", None),
        PackBinaryTestCase("invalid SourceCode CABLE", "60 3A F4 80 FF", None),
        PackBinaryTestCase("invalid SourceCode CABLE", "60 36 FA 80 FF", None),
        PackBinaryTestCase(
            "invalid SourceCode CABLE", "60 36 F4 80 2B", None
        ),  # has tuner category
        PackBinaryTestCase("invalid SourceCode TUNER", "60 A6 F4 C0 2B", None),
        PackBinaryTestCase("invalid SourceCode TUNER", "60 3A F4 C0 2B", None),
        PackBinaryTestCase("invalid SourceCode TUNER", "60 36 FA C0 2B", None),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_source_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc)


SIMPLE_VAUX_SOURCE = pack.VAUXSource(
    source_code=pack.SourceCode.CAMERA,
    tv_channel=None,
    tuner_category=None,
    source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
    field_count=60,
    bw_flag=pack.BlackAndWhiteFlag.COLOR,
    color_frames_id_valid=False,
    color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
)


@pytest.mark.parametrize(
    "tc",
    [
        # Check the combination of SourceCode and TV channel presence/value
        PackValidateCase(
            "SourceCode CAMERA has channel",
            replace(SIMPLE_VAUX_SOURCE, source_code=pack.SourceCode.CAMERA, tv_channel=5),
            "No TV channel may be provided for source CAMERA.",
        ),
        PackValidateCase(
            "SourceCode LINE_MUSE has channel",
            replace(SIMPLE_VAUX_SOURCE, source_code=pack.SourceCode.LINE_MUSE, tv_channel=5),
            "No TV channel may be provided for source LINE_MUSE.",
        ),
        PackValidateCase(
            "SourceCode LINE has channel",
            replace(SIMPLE_VAUX_SOURCE, source_code=pack.SourceCode.LINE, tv_channel=5),
            "No TV channel may be provided for source LINE.",
        ),
        PackValidateCase(
            "SourceCode CABLE channel missing",
            replace(SIMPLE_VAUX_SOURCE, source_code=pack.SourceCode.CABLE, tv_channel=None),
            "A TV channel must be provided for source CABLE.",
        ),
        PackValidateCase(
            "SourceCode CABLE channel too low",
            replace(SIMPLE_VAUX_SOURCE, source_code=pack.SourceCode.CABLE, tv_channel=0),
            "TV channel is out of range for source CABLE.",
        ),
        PackValidateCase(
            "SourceCode CABLE channel too high",
            replace(SIMPLE_VAUX_SOURCE, source_code=pack.SourceCode.CABLE, tv_channel=1000),
            "TV channel is out of range for source CABLE.",
        ),
        PackValidateCase(
            "SourceCode TUNER channel missing",
            replace(
                SIMPLE_VAUX_SOURCE,
                source_code=pack.SourceCode.TUNER,
                tv_channel=None,
                tuner_category=0x2B,
            ),
            "A TV channel must be provided for source TUNER.",
        ),
        PackValidateCase(
            "SourceCode TUNER channel too low",
            replace(
                SIMPLE_VAUX_SOURCE,
                source_code=pack.SourceCode.TUNER,
                tv_channel=0,
                tuner_category=0x2B,
            ),
            "TV channel is out of range for source TUNER.",
        ),
        PackValidateCase(
            "SourceCode TUNER channel too high",
            replace(
                SIMPLE_VAUX_SOURCE,
                source_code=pack.SourceCode.TUNER,
                tv_channel=1000,
                tuner_category=0x2B,
            ),
            "TV channel is out of range for source TUNER.",
        ),
        PackValidateCase(
            "SourceCode PRERECORDED_TAPE has channel",
            replace(SIMPLE_VAUX_SOURCE, source_code=pack.SourceCode.PRERECORDED_TAPE, tv_channel=5),
            "No TV channel may be provided for source PRERECORDED_TAPE.",
        ),
        PackValidateCase(
            "SourceCode None has channel",
            replace(SIMPLE_VAUX_SOURCE, source_code=None, tv_channel=5),
            "No TV channel may be provided for source None.",
        ),
        # Check that tuner categories are present or not, as needed.
        PackValidateCase(
            "tuner category missing",
            replace(
                SIMPLE_VAUX_SOURCE,
                source_code=pack.SourceCode.TUNER,
                tv_channel=50,
                tuner_category=None,
            ),
            "A tuner category was not provided for source TUNER.",
        ),
        PackValidateCase(
            "tuner category missing",
            replace(
                SIMPLE_VAUX_SOURCE,
                source_code=pack.SourceCode.CABLE,
                tv_channel=50,
                tuner_category=0x2B,
            ),
            "A tuner category was provided for source CABLE that is not a tuner.",
        ),
        # Other validations
        PackValidateCase(
            "source type missing",
            replace(SIMPLE_VAUX_SOURCE, source_type=None),
            "Source type is required.",
        ),
        PackValidateCase(
            "field count missing",
            replace(SIMPLE_VAUX_SOURCE, field_count=None),
            "Field count is required.",
        ),
        PackValidateCase(
            "field count not supported",
            replace(SIMPLE_VAUX_SOURCE, field_count=60),
            "Field count must be 50 for system SYS_625_50.",
            system=PAL,
        ),
        PackValidateCase(
            "field count not supported",
            replace(SIMPLE_VAUX_SOURCE, field_count=50),
            "Field count must be 60 for system SYS_525_60.",
            system=NTSC,
        ),
        PackValidateCase(
            "black and white flag missing",
            replace(SIMPLE_VAUX_SOURCE, bw_flag=None),
            "Black and white flag is required.",
        ),
        PackValidateCase(
            "color frames ID valid missing",
            replace(SIMPLE_VAUX_SOURCE, color_frames_id_valid=None),
            "Color frames ID valid is required.",
        ),
        PackValidateCase(
            "color frames ID missing",
            replace(SIMPLE_VAUX_SOURCE, color_frames_id=None),
            "Color frames ID is required.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_source_validate(tc: PackValidateCase) -> None:
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test",
            {
                "source_code": "TUNER",
                "tv_channel": "291",
                "tuner_category": "0x2B",
                "source_type": "STANDARD_DEFINITION_COMPRESSED_CHROMA",
                "field_count": "50",
                "bw_flag": "BLACK_AND_WHITE",
                "color_frames_id_valid": "TRUE",
                "color_frames_id": "CLF_5_6_FIELD",
            },
            pack.VAUXSource(
                source_code=pack.SourceCode.TUNER,
                tv_channel=291,
                tuner_category=0x2B,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=50,
                bw_flag=pack.BlackAndWhiteFlag.BLACK_AND_WHITE,
                color_frames_id_valid=True,
                color_frames_id=pack.ColorFramesID.CLF_5_6_FIELD,
            ),
        ),
        PackTextSuccessTestCase(
            "empty",
            {
                "source_code": "",
                "tv_channel": "",
                "tuner_category": "",
                "source_type": "",
                "field_count": "",
                "bw_flag": "",
                "color_frames_id_valid": "",
                "color_frames_id": "",
            },
            pack.VAUXSource(),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_source_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.VAUXSource)
