"""Test packs that store AAUX source control."""

from dataclasses import replace
from fractions import Fraction

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
            "basic success",
            "51 03 CF A0 FF",  # from my Sony DCR-TRV460, first audio channel block
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=None,
                genre_category=0x7F,
                direction=pack.Direction.FORWARD,
                playback_speed=Fraction(1),
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "basic success, empty channel",
            "51 03 FF A0 FF",  # from my Sony DCR-TRV460, second (empty) audio channel block
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.INVALID,
                insert_channel=None,
                genre_category=0x7F,
                direction=pack.Direction.FORWARD,
                playback_speed=Fraction(1),
                reserved=0x1,
            ),
        ),
        # Additional contrived/synthetic test cases:
        #
        # Test playback speeds:
        PackBinaryTestCase(
            "stopped playback speed",
            "51 03 CF 80 FF",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=None,
                genre_category=0x7F,
                direction=pack.Direction.FORWARD,
                playback_speed=Fraction(),
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "super slow < 1/16 playback speed",
            "51 03 CF 81 FF",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=None,
                genre_category=0x7F,
                direction=pack.Direction.FORWARD,
                playback_speed=Fraction(1, 32),
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "0 + 1/4 playback speed",
            "51 03 CF 8E FF",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=None,
                genre_category=0x7F,
                direction=pack.Direction.FORWARD,
                playback_speed=Fraction(1, 4),
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "1/2 + 3/32 playback speed",
            "51 03 CF 93 FF",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=None,
                genre_category=0x7F,
                direction=pack.Direction.FORWARD,
                playback_speed=Fraction(19, 32),
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "32 + 28 playback speed",
            "51 03 CF FE FF",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=None,
                genre_category=0x7F,
                direction=pack.Direction.FORWARD,
                playback_speed=Fraction(60),
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "unknown playback speed",
            "51 03 CF FF FF",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=None,
                genre_category=0x7F,
                direction=pack.Direction.FORWARD,
                playback_speed=None,
                reserved=0x1,
            ),
        ),
        # Other synthetic tests:
        PackBinaryTestCase(
            "various values (1)",
            "51 0A 8D 20 7F",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=pack.SourceSituation.SOURCE_WITH_AUDIENCE_RESTRICTIONS,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_3_OR_MORE,
                recording_start_point=False,
                recording_end_point=True,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=pack.InsertChannel.CHANNELS_3_4,
                genre_category=0x7F,
                direction=pack.Direction.REVERSE,
                playback_speed=Fraction(1),
                reserved=0x0,
            ),
        ),
        PackBinaryTestCase(
            "various values (2)",
            "51 93 6F C3 AA",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.ONE_GENERATION_ONLY,
                source_situation=None,
                input_source=pack.InputSource.DIGITAL,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=True,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.TWO_CHANNEL_INSERT,
                insert_channel=None,
                genre_category=0x2A,
                direction=pack.Direction.FORWARD,
                playback_speed=4 + Fraction(3, 4),
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "all bits set",
            "51 FF FF FF FF",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NOT_PERMITTED,
                source_situation=None,
                input_source=None,
                compression_count=None,
                recording_start_point=False,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.INVALID,
                insert_channel=None,
                genre_category=0x7F,
                direction=pack.Direction.FORWARD,
                playback_speed=None,
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "all bits mostly clear",
            "51 00 08 00 00",
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=pack.SourceSituation.SCRAMBLED_SOURCE_WITH_AUDIENCE_RESTRICTIONS,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=True,
                recording_end_point=True,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=pack.InsertChannel.CHANNEL_1,
                genre_category=0x00,
                direction=pack.Direction.REVERSE,
                playback_speed=Fraction(),
                reserved=0x0,
            ),
        ),
        # Some invalid values
        PackBinaryTestCase("invalid recording mode", "51 00 00 00 00", None),
    ],
    ids=lambda tc: tc.name,
)
def test_aaux_source_control_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc)


SIMPLE_AAUX_SOURCE_CONTROL = pack.AAUXSourceControl(
    copy_protection=pack.CopyProtection.NO_RESTRICTION,
    source_situation=None,
    input_source=pack.InputSource.ANALOG,
    compression_count=pack.CompressionCount.CMP_1,
    recording_start_point=False,
    recording_end_point=False,
    recording_mode=pack.AAUXRecordingMode.ORIGINAL,
    insert_channel=None,
    genre_category=0x7F,
    direction=pack.Direction.FORWARD,
    playback_speed=Fraction(1),
    reserved=0x1,
)


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase(
            "no copy protection",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, copy_protection=None),
            "Copy protection status is required.",
        ),
        PackValidateCase(
            "no recording start point",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, recording_start_point=None),
            "Recording start point is required.",
        ),
        PackValidateCase(
            "no recording end point",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, recording_end_point=None),
            "Recording end point is required.",
        ),
        PackValidateCase(
            "no recording mode",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, recording_mode=None),
            "Recording mode is required.",
        ),
        PackValidateCase(
            "no genre category",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, genre_category=None),
            "Genre category is required.",
        ),
        PackValidateCase(
            "genre category is too low",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, genre_category=-1),
            "Genre category is out of range.",
        ),
        PackValidateCase(
            "genre category is too high",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, genre_category=0x80),
            "Genre category is out of range.",
        ),
        PackValidateCase(
            "no direction",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, direction=None),
            "Direction field is required.",
        ),
        PackValidateCase(
            "invalid playback speed",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, playback_speed=Fraction(100)),
            "Unsupported playback speed selected.  Only certain fractional values allowed.",
        ),
        PackValidateCase(
            "no reserved",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, reserved=None),
            "Reserved field is required.",
        ),
        PackValidateCase(
            "reserved too low",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, reserved=-1),
            "Reserved field is out of range.",
        ),
        PackValidateCase(
            "reserved too high",
            replace(SIMPLE_AAUX_SOURCE_CONTROL, reserved=0x2),
            "Reserved field is out of range.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_aaux_source_control_validate(tc: PackValidateCase) -> None:
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test",
            {
                "copy_protection": "NO_RESTRICTION",
                "source_situation": "SOURCE_WITH_AUDIENCE_RESTRICTIONS",
                "input_source": "ANALOG",
                "compression_count": "CMP_1",
                "recording_start_point": "TRUE",
                "recording_end_point": "FALSE",
                "recording_mode": "ORIGINAL",
                "insert_channel": "CHANNEL_3",
                "genre_category": "0x2B",
                "direction": "FORWARD",
                "playback_speed": "1/2",
                "reserved": "0x1",
            },
            pack.AAUXSourceControl(
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=pack.SourceSituation.SOURCE_WITH_AUDIENCE_RESTRICTIONS,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=True,
                recording_end_point=False,
                recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                insert_channel=pack.InsertChannel.CHANNEL_3,
                genre_category=0x2B,
                direction=pack.Direction.FORWARD,
                playback_speed=Fraction(1, 2),
                reserved=0x1,
            ),
        ),
        PackTextSuccessTestCase(
            "empty",
            {
                "copy_protection": "",
                "source_situation": "",
                "input_source": "",
                "compression_count": "",
                "recording_start_point": "",
                "recording_end_point": "",
                "recording_mode": "",
                "insert_channel": "",
                "genre_category": "",
                "direction": "",
                "playback_speed": "",
                "reserved": "",
            },
            pack.AAUXSourceControl(),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_aaux_source_control_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.AAUXSourceControl)
