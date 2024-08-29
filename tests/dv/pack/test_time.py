from dataclasses import replace
from typing import cast

import pytest

import tests.dv.pack.test_base as test_base
import video_tools.dv.file_info as dv_file_info
import video_tools.dv.pack as pack
from tests.dv.pack.test_base import (
    PackBinaryTestCase,
    PackTextParseFailureTestCase,
    PackTextSuccessTestCase,
    PackValidateCase,
)

NTSC = dv_file_info.DVSystem.SYS_525_60
PAL = dv_file_info.DVSystem.SYS_625_50


# ======================== TIME PACK TESTS ========================

ZERO_TIMECODE = pack.TitleTimecode(
    hour=0,
    minute=0,
    second=0,
    frame=0,
    drop_frame=False,
    color_frame=pack.ColorFrame.UNSYNCHRONIZED,
    polarity_correction=pack.PolarityCorrection.EVEN,
    binary_group_flags=0x0,
    blank_flag=pack.BlankFlag.DISCONTINUOUS,
)

# Do most heavy testing on the TitleTimecode


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "success NTSC, no TITLE BINARY pack, blank flag continuous",
            "13 D5 B4 D7 D3",
            pack.TitleTimecode(
                hour=13,
                minute=57,
                second=34,
                frame=15,
                drop_frame=True,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.ODD,
                binary_group_flags=0x7,
                blank_flag=pack.BlankFlag.CONTINUOUS,
            ),
        ),
        PackBinaryTestCase(
            "success NTSC, drop frame True, do not drop 00:10:00;01",
            "13 41 00 10 00",
            pack.TitleTimecode(
                hour=0,
                minute=10,
                second=0,
                frame=1,
                drop_frame=True,
                color_frame=pack.ColorFrame.UNSYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.EVEN,
                binary_group_flags=0x0,
                blank_flag=pack.BlankFlag.DISCONTINUOUS,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "success PAL, drop frame False, do not drop 00:09:00;01",
            "13 01 00 09 00",
            pack.TitleTimecode(
                hour=0,
                minute=9,
                second=0,
                frame=1,
                drop_frame=False,
                color_frame=pack.ColorFrame.UNSYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.EVEN,
                binary_group_flags=0x0,
                blank_flag=pack.BlankFlag.DISCONTINUOUS,
            ),
            system=PAL,
        ),
        PackBinaryTestCase(
            "max bounds NTSC, no TITLE BINARY pack",
            "13 29 D9 D9 E3",
            pack.TitleTimecode(
                hour=23,
                minute=59,
                second=59,
                frame=29,
                drop_frame=False,
                color_frame=pack.ColorFrame.UNSYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.ODD,
                binary_group_flags=0x7,
                blank_flag=pack.BlankFlag.DISCONTINUOUS,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "max bounds PAL, no TITLE BINARY pack",
            "13 A4 D9 D9 E3",
            pack.TitleTimecode(
                hour=23,
                minute=59,
                second=59,
                frame=24,
                drop_frame=False,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.ODD,
                binary_group_flags=0x7,
                blank_flag=pack.BlankFlag.CONTINUOUS,
            ),
            system=PAL,
        ),
        PackBinaryTestCase("high frame tens", "13 30 59 59 23", None, system=NTSC),
        PackBinaryTestCase("high frame units", "13 1A 59 59 23", None, system=NTSC),
        PackBinaryTestCase("high second tens", "13 29 60 59 23", None, system=NTSC),
        PackBinaryTestCase("high second units", "13 29 4A 59 23", None, system=NTSC),
        PackBinaryTestCase("high minute tens", "13 29 59 60 23", None, system=NTSC),
        PackBinaryTestCase("high minute units", "13 29 59 4A 23", None, system=NTSC),
        PackBinaryTestCase("high hour tens", "13 29 59 59 30", None, system=NTSC),
        PackBinaryTestCase("high hour units", "13 29 59 59 1A", None, system=NTSC),
        PackBinaryTestCase("no dropout", "13 00 00 00 00", ZERO_TIMECODE, system=NTSC),
        PackBinaryTestCase("obvious dropout 1", "13 00 00 00 FF", None, system=NTSC),
        PackBinaryTestCase("obvious dropout 2", "13 00 00 FF FF", None, system=NTSC),
        PackBinaryTestCase("obvious dropout 3", "13 00 FF FF FF", None, system=NTSC),
        PackBinaryTestCase("obvious dropout 4", "13 FF FF FF FF", None, system=NTSC),
        # try setting the various high bits one by one
        PackBinaryTestCase(
            "CF NTSC",
            "13 80 00 00 00",
            replace(
                ZERO_TIMECODE,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                blank_flag=pack.BlankFlag.CONTINUOUS,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "CF PAL",
            "13 80 00 00 00",
            replace(
                ZERO_TIMECODE,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                blank_flag=pack.BlankFlag.CONTINUOUS,
            ),
            system=PAL,
        ),
        PackBinaryTestCase(
            "DF NTSC", "13 40 00 00 00", replace(ZERO_TIMECODE, drop_frame=True), system=NTSC
        ),
        PackBinaryTestCase("DF PAL", "13 40 00 00 00", None, system=PAL),
        PackBinaryTestCase(
            "PC NTSC",
            "13 00 80 00 00",
            replace(ZERO_TIMECODE, polarity_correction=pack.PolarityCorrection.ODD),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "PC PAL",
            "13 00 00 00 80",
            replace(ZERO_TIMECODE, polarity_correction=pack.PolarityCorrection.ODD),
            system=PAL,
        ),
        PackBinaryTestCase(
            "BGF0 NTSC",
            "13 00 00 80 00",
            replace(
                ZERO_TIMECODE,
                binary_group_flags=0x1,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "BGF0 PAL",
            "13 00 80 00 00",
            replace(
                ZERO_TIMECODE,
                binary_group_flags=0x1,
            ),
            system=PAL,
        ),
        PackBinaryTestCase(
            "BGF1 NTSC",
            "13 00 00 00 40",
            replace(
                ZERO_TIMECODE,
                binary_group_flags=0x2,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "BGF1 PAL",
            "13 00 00 00 40",
            replace(
                ZERO_TIMECODE,
                binary_group_flags=0x2,
            ),
            system=PAL,
        ),
        PackBinaryTestCase(
            "BGF2 NTSC",
            "13 00 00 00 80",
            replace(
                ZERO_TIMECODE,
                binary_group_flags=0x4,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "BGF2 PAL",
            "13 00 00 80 00",
            replace(
                ZERO_TIMECODE,
                binary_group_flags=0x4,
            ),
            system=PAL,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_title_timecode_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc, pack.TitleTimecode)


# Do some testing on the recording time, especially around optional values.
# Otherwise, we'll rely on the existing test cases of the title timecode


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "success NTSC, no TITLE BINARY pack",
            "63 D5 B4 D7 D3",
            pack.VAUXRecordingTime(
                hour=13,
                minute=57,
                second=34,
                frame=15,
                drop_frame=True,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.ODD,
                binary_group_flags=0x7,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "success NTSC, no frames",
            "63 FF B4 D7 D3",
            pack.VAUXRecordingTime(
                hour=13,
                minute=57,
                second=34,
                frame=None,
                drop_frame=True,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.ODD,
                binary_group_flags=0x7,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "success PAL, no frames, drop frame still set",
            "63 FF B4 D7 D3",
            pack.VAUXRecordingTime(
                hour=13,
                minute=57,
                second=34,
                frame=None,
                drop_frame=True,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.ODD,
                binary_group_flags=0x7,
            ),
            system=PAL,
        ),
        PackBinaryTestCase(
            "success, no time at all",
            "63 FF FF FF FF",
            pack.VAUXRecordingTime(
                hour=None,
                minute=None,
                second=None,
                frame=None,
                drop_frame=True,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.ODD,
                binary_group_flags=0x7,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase("high frame tens", "63 30 59 59 23", None, system=NTSC),
        PackBinaryTestCase("high frame units", "63 1A 59 59 23", None, system=NTSC),
        PackBinaryTestCase("high second tens", "63 29 60 59 23", None, system=NTSC),
        PackBinaryTestCase("high second units", "63 29 4A 59 23", None, system=NTSC),
        PackBinaryTestCase("high minute tens", "63 29 59 60 23", None, system=NTSC),
        PackBinaryTestCase("high minute units", "63 29 59 4A 23", None, system=NTSC),
        PackBinaryTestCase("high hour tens", "63 29 59 59 30", None, system=NTSC),
        PackBinaryTestCase("high hour units", "63 29 59 59 1A", None, system=NTSC),
        PackBinaryTestCase("obvious dropout 1", "63 00 00 00 FF", None, system=NTSC),
        PackBinaryTestCase("obvious dropout 2", "63 00 00 FF FF", None, system=NTSC),
        PackBinaryTestCase("obvious dropout 3", "63 00 FF FF FF", None, system=NTSC),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_recording_time_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc, pack.VAUXRecordingTime)


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "success NTSC, no frames",
            "53 FF B4 D7 D3",
            pack.AAUXRecordingTime(
                hour=13,
                minute=57,
                second=34,
                frame=None,
                drop_frame=True,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.ODD,
                binary_group_flags=0x7,
            ),
            system=NTSC,
        ),
        PackBinaryTestCase(
            "success, no time at all",
            "53 FF FF FF FF",
            pack.AAUXRecordingTime(
                hour=None,
                minute=None,
                second=None,
                frame=None,
                drop_frame=True,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.ODD,
                binary_group_flags=0x7,
            ),
            system=NTSC,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_aaux_recording_time_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc, pack.AAUXRecordingTime)


# For validation failures, again, we will make most test cases against TitleTimecode.  But we will
# again rely on the VAUX recording time in order to test optional scenarios.


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase(
            "mixed time field presence",
            replace(ZERO_TIMECODE, hour=None),
            "All main time fields must be fully present or fully absent.",
        ),
        PackValidateCase(
            "only frames given",
            replace(ZERO_TIMECODE, hour=None, minute=None, second=None, frame=10),
            "Frame numbers cannot be given if the rest of the time is missing.",
        ),
        PackValidateCase(
            "no time provided, and is required",
            replace(ZERO_TIMECODE, hour=None, minute=None, second=None, frame=None),
            "A time value is required but was not given.",
        ),
        PackValidateCase(
            "frame number missing, and is required",
            replace(ZERO_TIMECODE, hour=1, minute=2, second=3, frame=None),
            "A frame number must be given with the time value.",
        ),
        PackValidateCase(
            "drop frame missing",
            replace(ZERO_TIMECODE, drop_frame=None),
            "All auxiliary SMPTE timecode fields must be provided.",
        ),
        PackValidateCase(
            "color frame missing",
            replace(ZERO_TIMECODE, color_frame=None),
            "All auxiliary SMPTE timecode fields must be provided.",
        ),
        PackValidateCase(
            "polarity correction missing",
            replace(ZERO_TIMECODE, polarity_correction=None),
            "All auxiliary SMPTE timecode fields must be provided.",
        ),
        PackValidateCase(
            "binary group flags missing",
            replace(ZERO_TIMECODE, binary_group_flags=None),
            "All auxiliary SMPTE timecode fields must be provided.",
        ),
        PackValidateCase(
            "invalid time",
            replace(ZERO_TIMECODE, hour=1, minute=60, second=3, frame=10),
            "The time field has an invalid range.",
        ),
        PackValidateCase(
            "negative frame number",
            replace(ZERO_TIMECODE, frame=-1),
            "A negative frame number was provided.",
        ),
        PackValidateCase(
            "high NTSC frame rate",
            replace(ZERO_TIMECODE, frame=30),
            "The frame number is too high for the given NTSC frame rate.",
            system=NTSC,
        ),
        PackValidateCase(
            "high PAL frame rate",
            replace(ZERO_TIMECODE, frame=25),
            "The frame number is too high for the given PAL/SECAM frame rate.",
            system=PAL,
        ),
        PackValidateCase(
            "drop frame set on PAL",
            replace(ZERO_TIMECODE, drop_frame=True),
            "The drop frame flag was set, but this does not make sense for PAL/SECAM.",
            system=PAL,
        ),
        PackValidateCase(
            "dropped frame number provided",
            replace(ZERO_TIMECODE, minute=9, second=0, frame=0, drop_frame=True),
            "The drop frame flag was set, but a dropped frame number was provided.",
            system=NTSC,
        ),
        PackValidateCase(
            "dropped frame number provided",
            replace(ZERO_TIMECODE, minute=1, second=0, frame=1, drop_frame=True),
            "The drop frame flag was set, but a dropped frame number was provided.",
            system=NTSC,
        ),
        PackValidateCase(
            "binary group flags negative",
            replace(ZERO_TIMECODE, binary_group_flags=-1),
            "Binary group flags are out of range.",
            system=NTSC,
        ),
        PackValidateCase(
            "binary group flags positive",
            replace(ZERO_TIMECODE, binary_group_flags=0x8),
            "Binary group flags are out of range.",
            system=NTSC,
        ),
        PackValidateCase(
            "blank flag missing",
            replace(ZERO_TIMECODE, blank_flag=None),
            "A value for the blank flag must be provided.",
        ),
        PackValidateCase(
            "blank flag mismatch",
            replace(ZERO_TIMECODE, blank_flag=pack.BlankFlag.CONTINUOUS),
            "Blank flag integer value of 1 must be equal to the color frame flag integer "
            "value of 0, because they occupy the same physical bit positions on the tape.  "
            "Change one value to match the other.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_time_validate(tc: PackValidateCase) -> None:
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "starting_value,expectations,system",
    [
        # basic case, no overflows
        ["01:02:03;04", ["01:02:03;05", "01:02:03;06", "01:02:03;07", "01:02:03;08"], NTSC],
        # frames overflow
        ["01:02:03;28", ["01:02:03;29", "01:02:04;00", "01:02:04;01", "01:02:04;02"], NTSC],
        ["01:02:03:23", ["01:02:03:24", "01:02:04:00", "01:02:04:01", "01:02:04:02"], PAL],
        # drop frame handling
        ["01:01:59;28", ["01:01:59;29", "01:02:00;02", "01:02:00;03", "01:02:00;04"], NTSC],
        ["01:02:59;28", ["01:02:59;29", "01:03:00;02", "01:03:00;03", "01:03:00;04"], NTSC],
        ["01:08:59;28", ["01:08:59;29", "01:09:00;02", "01:09:00;03", "01:09:00;04"], NTSC],
        ["01:09:59;28", ["01:09:59;29", "01:10:00;00", "01:10:00;01", "01:10:00;02"], NTSC],
        # seconds overflow, NTSC but no drop frame
        ["01:02:59:29", ["01:03:00:00", "01:03:00:01", "01:03:00:02", "01:03:00:03"], NTSC],
        # minutes overflow
        ["01:59:59:29", ["02:00:00:00", "02:00:00:01", "02:00:00:02", "02:00:00:03"], NTSC],
        # hours overflow
        ["23:59:59:29", ["00:00:00:00", "00:00:00:01", "00:00:00:02", "00:00:00:03"], NTSC],
    ],
)
def test_time_increment(
    starting_value: str, expectations: list[str], system: dv_file_info.DVSystem
) -> None:
    val = replace(
        pack.TitleTimecode(), **pack.TitleTimecode.parse_text_value(None, starting_value)._asdict()
    )
    results = []
    for i in range(4):
        val = cast(pack.TitleTimecode, val.increment_frame(system))
        results.append(val.to_text_value(None, val.value_subset_for_text_field(None)))
    assert results == expectations


@pytest.mark.parametrize(
    "value,message,system",
    [
        [None, "Cannot increment a time pack with no time in it", NTSC],
        [
            "01:02:03;04",
            "Drop frame flag is set on PAL/SECAM video, which probably doesn't make sense.",
            PAL,
        ],
    ],
)
def test_time_increment_failures(value: str, message: str, system: dv_file_info.DVSystem) -> None:
    val = replace(
        pack.TitleTimecode(), **pack.TitleTimecode.parse_text_value(None, value)._asdict()
    )
    with pytest.raises(pack.PackValidationError, match=message):
        val.increment_frame(system)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test, drop frame",
            {
                None: "12:34:56;12",
                "color_frame": "SYNCHRONIZED",
                "polarity_correction": "EVEN",
                "binary_group_flags": "0x3",
                "blank_flag": "CONTINUOUS",
            },
            pack.TitleTimecode(
                hour=12,
                minute=34,
                second=56,
                frame=12,
                drop_frame=True,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.EVEN,
                binary_group_flags=0x3,
                blank_flag=pack.BlankFlag.CONTINUOUS,
            ),
        ),
        PackTextSuccessTestCase(
            "basic test, no drop frame",
            {
                None: "12:34:56:12",
                "color_frame": "SYNCHRONIZED",
                "polarity_correction": "EVEN",
                "binary_group_flags": "0x3",
                "blank_flag": "CONTINUOUS",
            },
            pack.TitleTimecode(
                hour=12,
                minute=34,
                second=56,
                frame=12,
                drop_frame=False,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.EVEN,
                binary_group_flags=0x3,
                blank_flag=pack.BlankFlag.CONTINUOUS,
            ),
        ),
        PackTextSuccessTestCase(
            "basic test, no frame",
            {
                None: "12:34:56",
                "color_frame": "SYNCHRONIZED",
                "polarity_correction": "EVEN",
                "binary_group_flags": "0x3",
                "blank_flag": "CONTINUOUS",
            },
            pack.TitleTimecode(
                hour=12,
                minute=34,
                second=56,
                drop_frame=True,
                color_frame=pack.ColorFrame.SYNCHRONIZED,
                polarity_correction=pack.PolarityCorrection.EVEN,
                binary_group_flags=0x3,
                blank_flag=pack.BlankFlag.CONTINUOUS,
            ),
        ),
        PackTextSuccessTestCase(
            "empty",
            {
                None: "",
                "color_frame": "",
                "polarity_correction": "",
                "binary_group_flags": "",
                "blank_flag": "",
            },
            pack.TitleTimecode(drop_frame=True),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_title_timecode_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.TitleTimecode)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextParseFailureTestCase(
            "invalid time pattern",
            {
                None: "blah",
            },
            "Parsing error while reading timecode blah",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_title_timecode_text_parse_failure(tc: PackTextParseFailureTestCase) -> None:
    test_base.run_pack_text_parse_failure_test_case(tc, pack.TitleTimecode)
