from dataclasses import dataclass, replace
from typing import cast

import pytest

import video_tools.dv.dif_pack as pack
import video_tools.dv.file_info as dv_file_info

NTSC = dv_file_info.DVSystem.SYS_525_60
PAL = dv_file_info.DVSystem.SYS_625_50

# ======================== REUSABLE TEST CASES ========================


@dataclass
class PackBinaryTestCase:
    name: str
    input: str
    parsed: pack.Pack | None
    output: str | None = None
    system: dv_file_info.DVSystem = NTSC


def run_pack_binary_test_case(tc: PackBinaryTestCase, cls: type[pack.Pack]) -> None:
    """Test round trip of a pack from binary, to parsed, and then back to binary."""
    input = bytes.fromhex(tc.input)
    p = cls.parse_binary(input, tc.system)
    assert p == tc.parsed
    if p:
        output = bytes.fromhex(tc.output) if tc.output is not None else input
        assert p.to_binary(tc.system) == output


@dataclass
class PackValidateCase:
    name: str
    input: pack.Pack
    failure: str
    system: dv_file_info.DVSystem = NTSC


def run_pack_validate_case(tc: PackValidateCase) -> None:
    """Test validation failures when writing a pack to binary."""
    with pytest.raises(pack.PackValidationError, match=tc.failure):
        tc.input.to_binary(tc.system)


# ======================== BASE CLASS EDGE CASE TESTING ========================
def test_base_pack_validation() -> None:
    with pytest.raises(AssertionError):
        # wrong header
        pack.NoInfo.parse_binary(bytes.fromhex("00 FF FF FF FF"), NTSC)
    with pytest.raises(AssertionError):
        # wrong length
        pack.NoInfo.parse_binary(bytes.fromhex("FF FF FF FF"), NTSC)


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
    run_pack_binary_test_case(tc, pack.TitleTimecode)


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
    run_pack_binary_test_case(tc, pack.VAUXRecordingTime)


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
    run_pack_binary_test_case(tc, pack.AAUXRecordingTime)


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
    run_pack_validate_case(tc)


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


# ======================== DATE PACK TESTS ========================


# Do most heavy testing on the VAUXRecordingDate


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic success",
            "62 D9 E7 48 97",
            pack.VAUXRecordingDate(
                year=1997,
                month=8,
                day=27,
                week=pack.Week.TUESDAY,
                time_zone_hours=19,
                time_zone_30_minutes=False,
                daylight_saving_time=pack.DaylightSavingTime.NORMAL,
                reserved=0x3,
            ),
        ),
        PackBinaryTestCase(
            "more basic success",
            "62 85 97 65 63",
            pack.VAUXRecordingDate(
                year=2063,
                month=5,
                day=17,
                week=pack.Week.WEDNESDAY,
                time_zone_hours=5,
                time_zone_30_minutes=True,
                daylight_saving_time=pack.DaylightSavingTime.NORMAL,
                reserved=0x2,
            ),
        ),
        # bounds testing: Y2K
        PackBinaryTestCase(
            "Y2K rollover: last 20th century year, DST, 09:00 TZ, reserved 0x0",
            "62 49 17 05 99",
            pack.VAUXRecordingDate(
                year=1999,
                month=5,
                day=17,
                week=pack.Week.SUNDAY,
                time_zone_hours=9,
                time_zone_30_minutes=False,
                daylight_saving_time=pack.DaylightSavingTime.DST,
                reserved=0x0,
            ),
        ),
        PackBinaryTestCase(
            "Y2K rollover: first 21th century year, DST, 09:00 TZ, reserved 0x1",
            "62 21 57 45 00",
            pack.VAUXRecordingDate(
                year=2000,
                month=5,
                day=17,
                week=pack.Week.TUESDAY,
                time_zone_hours=21,
                time_zone_30_minutes=True,
                daylight_saving_time=pack.DaylightSavingTime.DST,
                reserved=0x1,
            ),
        ),
        PackBinaryTestCase(
            "Y2K rollover: first 20th century year",
            "62 49 17 A5 75",
            pack.VAUXRecordingDate(
                year=1975,
                month=5,
                day=17,
                week=pack.Week.FRIDAY,
                time_zone_hours=9,
                time_zone_30_minutes=False,
                daylight_saving_time=pack.DaylightSavingTime.DST,
                reserved=0x0,
            ),
        ),
        PackBinaryTestCase(
            "Y2K rollover: last 21th century year",
            "62 49 17 65 74",
            pack.VAUXRecordingDate(
                year=2074,
                month=5,
                day=17,
                week=pack.Week.WEDNESDAY,
                time_zone_hours=9,
                time_zone_30_minutes=False,
                daylight_saving_time=pack.DaylightSavingTime.DST,
                reserved=0x0,
            ),
        ),
        # bounds testing: general
        PackBinaryTestCase(
            "max bounds",
            "62 23 31 12 74",
            pack.VAUXRecordingDate(
                year=2074,
                month=12,
                day=31,
                week=pack.Week.SUNDAY,
                time_zone_hours=23,
                time_zone_30_minutes=True,
                daylight_saving_time=pack.DaylightSavingTime.DST,
                reserved=0x0,
            ),
        ),
        PackBinaryTestCase(
            "min bounds",
            "62 C0 C1 41 75",
            pack.VAUXRecordingDate(
                year=1975,
                month=1,
                day=1,
                week=pack.Week.TUESDAY,
                time_zone_hours=0,
                time_zone_30_minutes=False,
                daylight_saving_time=pack.DaylightSavingTime.NORMAL,
                reserved=0x3,
            ),
        ),
        # bounds testing: week day
        PackBinaryTestCase(
            "min weekday",
            "62 C0 D5 05 00",
            pack.VAUXRecordingDate(
                year=2000,
                month=5,
                day=15,
                week=pack.Week.SUNDAY,
                time_zone_hours=0,
                time_zone_30_minutes=False,
                daylight_saving_time=pack.DaylightSavingTime.NORMAL,
                reserved=0x3,
            ),
        ),
        PackBinaryTestCase(
            "max weekday",
            "62 C0 E1 C5 00",
            pack.VAUXRecordingDate(
                year=2000,
                month=5,
                day=21,
                week=pack.Week.SATURDAY,
                time_zone_hours=0,
                time_zone_30_minutes=False,
                daylight_saving_time=pack.DaylightSavingTime.NORMAL,
                reserved=0x3,
            ),
        ),
        # optionality
        PackBinaryTestCase(
            "no time zone or week",
            "62 FF E1 E5 01",
            pack.VAUXRecordingDate(
                year=2001,
                month=5,
                day=21,
                week=None,
                time_zone_hours=None,
                time_zone_30_minutes=None,
                daylight_saving_time=None,
                reserved=0x3,
            ),
        ),
        PackBinaryTestCase(
            "no date, but has time zone",
            "62 21 FF FF FF",
            pack.VAUXRecordingDate(
                year=None,
                month=None,
                day=None,
                week=None,
                time_zone_hours=21,
                time_zone_30_minutes=True,
                daylight_saving_time=pack.DaylightSavingTime.DST,
                reserved=0x3,
            ),
        ),
        PackBinaryTestCase(
            "empty pack",
            "62 FF FF FF FF",
            pack.VAUXRecordingDate(
                year=None,
                month=None,
                day=None,
                week=None,
                time_zone_hours=None,
                time_zone_30_minutes=None,
                daylight_saving_time=None,
                reserved=0x3,
            ),
        ),
        # test validations that are in binary parsing, not in validate
        PackBinaryTestCase("high time zone tens", "62 30 31 12 74", None, system=NTSC),
        PackBinaryTestCase("high time zone units", "62 1A 31 12 74", None, system=NTSC),
        PackBinaryTestCase("high day units", "62 23 2A 12 74", None, system=NTSC),
        PackBinaryTestCase("high month units", "62 23 25 0A 74", None, system=NTSC),
        PackBinaryTestCase("high year tens", "62 23 31 12 A0", None, system=NTSC),
        PackBinaryTestCase("high year units", "62 23 31 12 7A", None, system=NTSC),
        PackBinaryTestCase("obvious dropout 1", "62 D9 E7 48 FF", None, system=NTSC),
        PackBinaryTestCase("obvious dropout 2", "62 D9 E7 FF FF", None, system=NTSC),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_recording_date_binary(tc: PackBinaryTestCase) -> None:
    run_pack_binary_test_case(tc, pack.VAUXRecordingDate)


# Just a quick test to check that AAUX recording date is also set up right


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic success",
            "52 D9 E7 48 97",
            pack.AAUXRecordingDate(
                year=1997,
                month=8,
                day=27,
                week=pack.Week.TUESDAY,
                time_zone_hours=19,
                time_zone_30_minutes=False,
                daylight_saving_time=pack.DaylightSavingTime.NORMAL,
                reserved=0x3,
            ),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_aaux_recording_date_binary(tc: PackBinaryTestCase) -> None:
    run_pack_binary_test_case(tc, pack.AAUXRecordingDate)


# For validation failures, again, we will only make the test cases against VAUXRecordingDate.

ZERO_DATE = pack.VAUXRecordingDate(
    year=2000,
    month=1,
    day=1,
    week=pack.Week.FRIDAY,
    time_zone_hours=0,
    time_zone_30_minutes=True,
    daylight_saving_time=pack.DaylightSavingTime.DST,
    reserved=0x0,
)


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase(
            "mixed date field presence",
            replace(ZERO_DATE, month=None),
            "All main date fields must be fully present or fully absent.",
        ),
        PackValidateCase(
            "only weekday given",
            replace(ZERO_DATE, year=None, month=None, day=None, week=pack.Week.SUNDAY),
            "A weekday must not be provided if the date is otherwise absent.",
        ),
        PackValidateCase(
            "zero date fields: day",
            replace(ZERO_DATE, year=2000, month=1, day=0, week=None),
            "The date field has an invalid range.",
        ),
        PackValidateCase(
            "zero date fields: month",
            replace(ZERO_DATE, year=2000, month=0, day=1, week=None),
            "The date field has an invalid range.",
        ),
        PackValidateCase(
            "invalid date",
            replace(ZERO_DATE, year=2000, month=2, day=30, week=None),
            "The date field has an invalid range.",
        ),
        PackValidateCase(
            "wrong weekday",
            replace(ZERO_DATE, week=pack.Week.WEDNESDAY),
            "The weekday is incorrect for the given date.",
        ),
        PackValidateCase(
            "year too high",
            replace(ZERO_DATE, year=2075, week=None),
            "The year is too far into the future or the past.",
        ),
        PackValidateCase(
            "year too low",
            replace(ZERO_DATE, year=1974, week=None),
            "The year is too far into the future or the past.",
        ),
        PackValidateCase(
            "mixed time zone field presence",
            replace(ZERO_DATE, daylight_saving_time=None),
            "All main time zone fields must be fully present or fully absent.",
        ),
        PackValidateCase(
            "negative time zone hours",
            replace(ZERO_DATE, time_zone_hours=-1),
            "Time zone hours are out of range.",
        ),
        PackValidateCase(
            "high time zone hours",
            replace(ZERO_DATE, time_zone_hours=24),
            "Time zone hours are out of range.",
        ),
        PackValidateCase(
            "reserved is missing",
            replace(ZERO_DATE, reserved=None),
            "Reserved bits are required.  They should be 0x3 per the standard.",
        ),
        PackValidateCase(
            "reserved is negative",
            replace(ZERO_DATE, reserved=-1),
            "Reserved bits are out of range.",
        ),
        PackValidateCase(
            "reserved is too high",
            replace(ZERO_DATE, reserved=0x4),
            "Reserved bits are out of range.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_date_validate(tc: PackValidateCase) -> None:
    run_pack_validate_case(tc)


# ======================== BINARY GROUP PACK TESTS ========================


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic test",
            "14 12 34 56 78",
            pack.TitleBinaryGroup(value=bytes.fromhex("12 34 56 78")),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_title_binary_group_binary(tc: PackBinaryTestCase) -> None:
    run_pack_binary_test_case(tc, pack.TitleBinaryGroup)


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic test", "54 12 34 56 78", pack.AAUXBinaryGroup(value=bytes.fromhex("12 34 56 78"))
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_aaux_binary_group_binary(tc: PackBinaryTestCase) -> None:
    run_pack_binary_test_case(tc, pack.AAUXBinaryGroup)


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic test", "64 12 34 56 78", pack.VAUXBinaryGroup(value=bytes.fromhex("12 34 56 78"))
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_binary_group_binary(tc: PackBinaryTestCase) -> None:
    run_pack_binary_test_case(tc, pack.VAUXBinaryGroup)


# Only test TitleBinaryGroup, since the others share the same base class.


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase(
            "no value", pack.TitleBinaryGroup(), "A binary group value was not provided."
        ),
        PackValidateCase(
            "wrong length",
            pack.TitleBinaryGroup(value=b"ab"),
            "The binary group has the wrong length: expected 4 bytes but got 2.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_title_binary_group_validate(tc: PackValidateCase) -> None:
    run_pack_validate_case(tc)


# ======================== NO INFO PACK TESTS ========================


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase("basic test", "FF FF FF FF FF", pack.NoInfo()),
        PackBinaryTestCase("random bytes", "FF 12 34 56 78", pack.NoInfo(), "FF FF FF FF FF"),
    ],
    ids=lambda tc: tc.name,
)
def test_no_info_binary(tc: PackBinaryTestCase) -> None:
    run_pack_binary_test_case(tc, pack.NoInfo)
