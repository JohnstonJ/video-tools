"""Test packs that store AAUX sources."""

from dataclasses import replace

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
            "61 03 80 FC FF",  # from my Sony DCR-TRV460
            pack.VAUXSourceControl(
                broadcast_system=0x0,
                display_mode=0x0,
                frame_field=pack.FrameField.BOTH,
                first_second=1,
                frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                interlaced=True,
                still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                still_camera_picture=False,
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                genre_category=0x7F,
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "DVCPRO50 sample",
            # DVCPRO50 color bars from https://archive.org/details/SMPTEColorBarsBadTracking
            "61 33 C8 FC FF",
            pack.VAUXSourceControl(
                broadcast_system=0x0,
                display_mode=0x0,
                frame_field=pack.FrameField.BOTH,
                first_second=1,
                frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                interlaced=True,
                still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                still_camera_picture=False,
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=None,
                input_source=None,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                genre_category=0x7F,
                reserved=0x7,
            ),
        ),
        # Additional contrived/synthetic test cases:
        PackBinaryTestCase(
            "various values (1)",
            "61 0A ED AA 2A",
            pack.VAUXSourceControl(
                broadcast_system=0x2,
                display_mode=0x5,
                frame_field=pack.FrameField.BOTH,
                first_second=2,
                frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                interlaced=False,
                still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                still_camera_picture=True,
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=pack.SourceSituation.SOURCE_WITH_AUDIENCE_RESTRICTIONS,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_3_OR_MORE,
                recording_start_point=False,
                recording_mode=pack.VAUXRecordingMode.INSERT,
                genre_category=0x2A,
                reserved=0x6,
            ),
        ),
        PackBinaryTestCase(
            "various values (2)",
            "61 93 02 55 BB",
            pack.VAUXSourceControl(
                broadcast_system=0x1,
                display_mode=0x2,
                frame_field=pack.FrameField.ONLY_ONE,
                first_second=1,
                frame_change=pack.FrameChange.SAME_AS_PREVIOUS,
                interlaced=True,
                still_field_picture=pack.StillFieldPicture.NO_GAP,
                still_camera_picture=False,
                copy_protection=pack.CopyProtection.ONE_GENERATION_ONLY,
                source_situation=None,
                input_source=pack.InputSource.DIGITAL,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=True,
                recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                genre_category=0x3B,
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "all bits set",
            "61 FF FF FF FF",
            pack.VAUXSourceControl(
                broadcast_system=0x3,
                display_mode=0x7,
                frame_field=pack.FrameField.BOTH,
                first_second=1,
                frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                interlaced=True,
                still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                still_camera_picture=False,
                copy_protection=pack.CopyProtection.NOT_PERMITTED,
                source_situation=None,
                input_source=None,
                compression_count=None,
                recording_start_point=False,
                recording_mode=pack.VAUXRecordingMode.INVALID_RECORDING,
                genre_category=0x7F,
                reserved=0x7,
            ),
        ),
        PackBinaryTestCase(
            "all bits clear",
            "61 00 00 00 00",
            pack.VAUXSourceControl(
                broadcast_system=0x0,
                display_mode=0x0,
                frame_field=pack.FrameField.ONLY_ONE,
                first_second=2,
                frame_change=pack.FrameChange.SAME_AS_PREVIOUS,
                interlaced=False,
                still_field_picture=pack.StillFieldPicture.NO_GAP,
                still_camera_picture=True,
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=pack.SourceSituation.SCRAMBLED_SOURCE_WITH_AUDIENCE_RESTRICTIONS,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=True,
                recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                genre_category=0x00,
                reserved=0x0,
            ),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_source_control_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc)


SIMPLE_VAUX_SOURCE_CONTROL = pack.VAUXSourceControl(
    broadcast_system=0x0,
    display_mode=0x0,
    frame_field=pack.FrameField.BOTH,
    first_second=1,
    frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
    interlaced=True,
    still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
    still_camera_picture=False,
    copy_protection=pack.CopyProtection.NO_RESTRICTION,
    source_situation=None,
    input_source=pack.InputSource.ANALOG,
    compression_count=pack.CompressionCount.CMP_1,
    recording_start_point=False,
    recording_mode=pack.VAUXRecordingMode.ORIGINAL,
    genre_category=0x7F,
    reserved=0x1,
)


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase(
            "no broadcast system",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, broadcast_system=None),
            "A broadcast system is required.",
        ),
        PackValidateCase(
            "broadcast system too low",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, broadcast_system=-1),
            "Broadcast system is out of range.",
        ),
        PackValidateCase(
            "broadcast system too high",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, broadcast_system=0x4),
            "Broadcast system is out of range.",
        ),
        PackValidateCase(
            "no display mode system",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, display_mode=None),
            "A display mode is required.",
        ),
        PackValidateCase(
            "display mode too low",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, display_mode=-1),
            "Display mode is out of range.",
        ),
        PackValidateCase(
            "display mode too high",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, display_mode=0x8),
            "Display mode is out of range.",
        ),
        PackValidateCase(
            "no frame field",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, frame_field=None),
            "A frame field is required.",
        ),
        PackValidateCase(
            "no first second value",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, first_second=None),
            "A first second value is required.",
        ),
        PackValidateCase(
            "first second value too low",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, first_second=0),
            "The first second value must be 1 or 2 depending on which field is first.",
        ),
        PackValidateCase(
            "first second value too high",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, first_second=3),
            "The first second value must be 1 or 2 depending on which field is first.",
        ),
        PackValidateCase(
            "no frame change",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, frame_change=None),
            "A frame change value is required.",
        ),
        PackValidateCase(
            "no interlaced",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, interlaced=None),
            "An interlaced field value is required.",
        ),
        PackValidateCase(
            "no still field picture",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, still_field_picture=None),
            "A still field picture value is required.",
        ),
        PackValidateCase(
            "no still camera picture",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, still_camera_picture=None),
            "A still camera picture value is required.",
        ),
        PackValidateCase(
            "no copy protection",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, copy_protection=None),
            "Copy protection status is required.",
        ),
        PackValidateCase(
            "no recording start point",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, recording_start_point=None),
            "Recording start point is required.",
        ),
        PackValidateCase(
            "no recording mode",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, recording_mode=None),
            "Recording mode is required.",
        ),
        PackValidateCase(
            "no genre category",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, genre_category=None),
            "Genre category is required.",
        ),
        PackValidateCase(
            "genre category is too low",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, genre_category=-1),
            "Genre category is out of range.",
        ),
        PackValidateCase(
            "genre category is too high",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, genre_category=0x80),
            "Genre category is out of range.",
        ),
        PackValidateCase(
            "no reserved",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, reserved=None),
            "Reserved field is required.",
        ),
        PackValidateCase(
            "reserved too low",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, reserved=-1),
            "Reserved field is out of range.",
        ),
        PackValidateCase(
            "reserved too high",
            replace(SIMPLE_VAUX_SOURCE_CONTROL, reserved=0x8),
            "Reserved field is out of range.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_source_control_validate(tc: PackValidateCase) -> None:
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test",
            {
                "broadcast_system": "0x1",
                "display_mode": "0x2",
                "frame_field": "BOTH",
                "first_second": "1",
                "frame_change": "DIFFERENT_FROM_PREVIOUS",
                "interlaced": "TRUE",
                "still_field_picture": "TWICE_FRAME_TIME",
                "still_camera_picture": "FALSE",
                "copy_protection": "NO_RESTRICTION",
                "source_situation": "SOURCE_WITH_AUDIENCE_RESTRICTIONS",
                "input_source": "ANALOG",
                "compression_count": "CMP_1",
                "recording_start_point": "FALSE",
                "recording_mode": "ORIGINAL",
                "genre_category": "0x7F",
                "reserved": "0x1",
            },
            pack.VAUXSourceControl(
                broadcast_system=0x1,
                display_mode=0x2,
                frame_field=pack.FrameField.BOTH,
                first_second=1,
                frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                interlaced=True,
                still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                still_camera_picture=False,
                copy_protection=pack.CopyProtection.NO_RESTRICTION,
                source_situation=pack.SourceSituation.SOURCE_WITH_AUDIENCE_RESTRICTIONS,
                input_source=pack.InputSource.ANALOG,
                compression_count=pack.CompressionCount.CMP_1,
                recording_start_point=False,
                recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                genre_category=0x7F,
                reserved=0x1,
            ),
        ),
        PackTextSuccessTestCase(
            "empty",
            {
                "broadcast_system": "",
                "display_mode": "",
                "frame_field": "",
                "first_second": "",
                "frame_change": "",
                "interlaced": "",
                "still_field_picture": "",
                "still_camera_picture": "",
                "copy_protection": "",
                "source_situation": "",
                "input_source": "",
                "compression_count": "",
                "recording_start_point": "",
                "recording_mode": "",
                "genre_category": "",
                "reserved": "",
            },
            pack.VAUXSourceControl(),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_source_control_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.VAUXSourceControl)
