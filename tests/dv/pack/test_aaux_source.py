"""Test packs that store AAUX sources."""

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
            "50 CE 30 C0 D1",  # from my Sony DCR-TRV460, first audio channel block
            pack.AAUXSource(
                sample_frequency=32000,
                quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
                audio_samples_per_frame=1067,
                locked_mode=pack.LockedMode.UNLOCKED,
                stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                audio_block_channel_count=2,
                audio_mode=0x0,
                audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                multi_language=False,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                emphasis_on=False,
                emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
            ),
        ),
        PackBinaryTestCase(
            "basic success",
            "50 CE 3F C0 D1",  # from my Sony DCR-TRV460, second (empty) audio channel block
            pack.AAUXSource(
                sample_frequency=32000,
                quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
                audio_samples_per_frame=1067,
                locked_mode=pack.LockedMode.UNLOCKED,
                stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                audio_block_channel_count=2,
                audio_mode=0xF,  # no information (I guess means this channel is empty)
                audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                multi_language=False,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                emphasis_on=False,
                emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
            ),
        ),
        # Additional contrived/synthetic test cases:
        PackBinaryTestCase(
            "various values (1)",
            "50 40 B5 E0 C8",
            pack.AAUXSource(
                sample_frequency=44100,
                quantization=pack.AudioQuantization.LINEAR_16_BIT,
                audio_samples_per_frame=1742,
                locked_mode=pack.LockedMode.LOCKED,
                stereo_mode=pack.StereoMode.LUMPED_AUDIO,
                audio_block_channel_count=2,
                audio_mode=0x5,
                audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                multi_language=False,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=50,
                emphasis_on=False,
                emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
            ),
            system=PAL,
        ),
        PackBinaryTestCase(
            "various values (2)",
            "50 E8 0A 82 02",
            pack.AAUXSource(
                sample_frequency=48000,
                quantization=pack.AudioQuantization.LINEAR_20_BIT,
                audio_samples_per_frame=1620,
                locked_mode=pack.LockedMode.UNLOCKED,
                stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                audio_block_channel_count=1,
                audio_mode=0xA,
                audio_block_pairing=pack.AudioBlockPairing.PAIRED,
                multi_language=True,
                source_type=pack.SourceType.ANALOG_HIGH_DEFINITION_1125_1250,
                field_count=60,
                emphasis_on=True,
                emphasis_time_constant=pack.EmphasisTimeConstant.RESERVED,
            ),
            system=NTSC,
        ),
        # Try some invalid values
        PackBinaryTestCase("invalid sample frequency", "50 CE 30 C0 D9", None),
        PackBinaryTestCase("invalid one_1 bit", "50 8E 30 C0 D1", None),
        PackBinaryTestCase("invalid one_2 bit", "50 CE 30 40 D1", None),
        PackBinaryTestCase("invalid audio samples per frame", "50 DC 30 C0 D1", None),
        PackBinaryTestCase("invalid block channel count frequency", "50 CE 50 C0 D1", None),
    ],
    ids=lambda tc: tc.name,
)
def test_aaux_source_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc)


SIMPLE_AAUX_SOURCE = pack.AAUXSource(
    sample_frequency=32000,
    quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
    audio_samples_per_frame=1067,
    locked_mode=pack.LockedMode.UNLOCKED,
    stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
    audio_block_channel_count=2,
    audio_mode=0x0,
    audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
    multi_language=False,
    source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
    field_count=60,
    emphasis_on=False,
    emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
)


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase(
            "no sample frequency",
            replace(SIMPLE_AAUX_SOURCE, sample_frequency=None),
            "Audio sample frequency is required.",
        ),
        PackValidateCase(
            "invalid sample frequency",
            replace(SIMPLE_AAUX_SOURCE, sample_frequency=1234),
            "Audio sample frequency of 1234 is not supported.",
        ),
        PackValidateCase(
            "no quantization",
            replace(SIMPLE_AAUX_SOURCE, quantization=None),
            "Audio quantization is required.",
        ),
        PackValidateCase(
            "no audio samples per frame",
            replace(SIMPLE_AAUX_SOURCE, audio_samples_per_frame=None),
            "Audio samples per frame is required.",
        ),
        PackValidateCase(
            "invalid audio samples per frame: low end",
            replace(SIMPLE_AAUX_SOURCE, audio_samples_per_frame=1052),
            "Audio samples per frame is out of range.",
        ),
        PackValidateCase(
            "invalid audio samples per frame: high end",
            replace(SIMPLE_AAUX_SOURCE, audio_samples_per_frame=1081),
            "Audio samples per frame is out of range.",
        ),
        PackValidateCase(
            "no locked mode",
            replace(SIMPLE_AAUX_SOURCE, locked_mode=None),
            "Audio locked mode is required.",
        ),
        PackValidateCase(
            "no stereo mode",
            replace(SIMPLE_AAUX_SOURCE, stereo_mode=None),
            "Stereo mode enumeration value is required.",
        ),
        PackValidateCase(
            "no audio block channel count",
            replace(SIMPLE_AAUX_SOURCE, audio_block_channel_count=None),
            "Audio block channel count is required.",
        ),
        PackValidateCase(
            "audio block channel count too low",
            replace(SIMPLE_AAUX_SOURCE, audio_block_channel_count=0),
            "Audio block channel count must be 1 or 2.",
        ),
        PackValidateCase(
            "audio block channel count too high",
            replace(SIMPLE_AAUX_SOURCE, audio_block_channel_count=3),
            "Audio block channel count must be 1 or 2.",
        ),
        PackValidateCase(
            "no audio mode",
            replace(SIMPLE_AAUX_SOURCE, audio_mode=None),
            "Audio mode is required.",
        ),
        PackValidateCase(
            "audio mode too low",
            replace(SIMPLE_AAUX_SOURCE, audio_mode=-1),
            "Audio mode is out of range.",
        ),
        PackValidateCase(
            "audio mode too high",
            replace(SIMPLE_AAUX_SOURCE, audio_mode=0x10),
            "Audio mode is out of range.",
        ),
        PackValidateCase(
            "no audio block pairing",
            replace(SIMPLE_AAUX_SOURCE, audio_block_pairing=None),
            "Audio block pairing is required.",
        ),
        PackValidateCase(
            "no multi-language flag",
            replace(SIMPLE_AAUX_SOURCE, multi_language=None),
            "Multi-language flag is required.",
        ),
        PackValidateCase(
            "no source type",
            replace(SIMPLE_AAUX_SOURCE, source_type=None),
            "Source type is required.",
        ),
        PackValidateCase(
            "no field count",
            replace(SIMPLE_AAUX_SOURCE, field_count=None),
            "Field count is required.",
        ),
        PackValidateCase(
            "invalid field count for NTSC",
            replace(SIMPLE_AAUX_SOURCE, audio_samples_per_frame=1053, field_count=50),
            "Field count must be 60 for system SYS_525_60.",
            system=NTSC,
        ),
        PackValidateCase(
            "invalid field count for PAL",
            replace(SIMPLE_AAUX_SOURCE, audio_samples_per_frame=1264, field_count=60),
            "Field count must be 50 for system SYS_625_50.",
            system=PAL,
        ),
        PackValidateCase(
            "no emphasis on",
            replace(SIMPLE_AAUX_SOURCE, emphasis_on=None),
            "Emphasis on is required.",
        ),
        PackValidateCase(
            "no emphasis time constant",
            replace(SIMPLE_AAUX_SOURCE, emphasis_time_constant=None),
            "Emphasis time constant is required.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_aaux_source_validate(tc: PackValidateCase) -> None:
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test",
            {
                "sample_frequency": "32000",
                "quantization": "NONLINEAR_12_BIT",
                "audio_samples_per_frame": "1060",
                "locked_mode": "UNLOCKED",
                "stereo_mode": "MULTI_STEREO_AUDIO",
                "audio_block_channel_count": "2",
                "audio_mode": "0x1",
                "audio_block_pairing": "INDEPENDENT",
                "multi_language": "TRUE",
                "field_count": "60",
                "source_type": "STANDARD_DEFINITION_COMPRESSED_CHROMA",
                "emphasis_on": "FALSE",
                "emphasis_time_constant": "E_50_15",
            },
            pack.AAUXSource(
                sample_frequency=32000,
                quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
                audio_samples_per_frame=1060,
                locked_mode=pack.LockedMode.UNLOCKED,
                stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                audio_block_channel_count=2,
                audio_mode=0x1,
                audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                multi_language=True,
                source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                field_count=60,
                emphasis_on=False,
                emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
            ),
        ),
        PackTextSuccessTestCase(
            "empty",
            {
                "sample_frequency": "",
                "quantization": "",
                "audio_samples_per_frame": "",
                "locked_mode": "",
                "stereo_mode": "",
                "audio_block_channel_count": "",
                "audio_mode": "",
                "audio_block_pairing": "",
                "multi_language": "",
                "field_count": "",
                "source_type": "",
                "emphasis_on": "",
                "emphasis_time_constant": "",
            },
            pack.AAUXSource(),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_aaux_source_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.AAUXSource)
