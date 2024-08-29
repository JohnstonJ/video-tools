"""Test packs that store dates."""

from dataclasses import replace

import pytest

import tests.dv.pack.test_base as test_base
import video_tools.dv.pack as pack
from tests.dv.pack.test_base import (
    PackBinaryTestCase,
    PackTextParseFailureTestCase,
    PackTextSuccessTestCase,
    PackValidateCase,
)

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
        PackBinaryTestCase("high time zone tens", "62 30 31 12 74", None),
        PackBinaryTestCase("high time zone units", "62 1A 31 12 74", None),
        PackBinaryTestCase("high day units", "62 23 2A 12 74", None),
        PackBinaryTestCase("high month units", "62 23 25 0A 74", None),
        PackBinaryTestCase("high year tens", "62 23 31 12 A0", None),
        PackBinaryTestCase("high year units", "62 23 31 12 7A", None),
        PackBinaryTestCase("obvious dropout 1", "62 D9 E7 48 FF", None),
        PackBinaryTestCase("obvious dropout 2", "62 D9 E7 FF FF", None),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_recording_date_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc, pack.VAUXRecordingDate)


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
    test_base.run_pack_binary_test_case(tc, pack.AAUXRecordingDate)


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
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test",
            {
                None: "2024-04-07",
                "week": "TUESDAY",
                "tz": "21:30",
                "dst": "DST",
                "reserved": "0x2",
            },
            pack.VAUXRecordingDate(
                year=2024,
                month=4,
                day=7,
                week=pack.Week.TUESDAY,
                time_zone_hours=21,
                time_zone_30_minutes=True,
                daylight_saving_time=pack.DaylightSavingTime.DST,
                reserved=0x2,
            ),
        ),
        PackTextSuccessTestCase(
            "time zone not 30 minutes",
            {
                None: "2024-04-07",
                "week": "TUESDAY",
                "tz": "21:00",
                "dst": "NORMAL",
                "reserved": "0x2",
            },
            pack.VAUXRecordingDate(
                year=2024,
                month=4,
                day=7,
                week=pack.Week.TUESDAY,
                time_zone_hours=21,
                time_zone_30_minutes=False,
                daylight_saving_time=pack.DaylightSavingTime.NORMAL,
                reserved=0x2,
            ),
        ),
        PackTextSuccessTestCase(
            "empty",
            {
                None: "",
                "week": "",
                "tz": "",
                "dst": "",
                "reserved": "",
            },
            pack.VAUXRecordingDate(),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_recording_date_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.VAUXRecordingDate)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextParseFailureTestCase(
            "invalid date pattern",
            {
                None: "blah",
            },
            "Parsing error while reading date blah.",
        ),
        PackTextParseFailureTestCase(
            "invalid time zone",
            {
                "tz": "blah",
            },
            "Parsing error while reading time zone blah.",
        ),
        PackTextParseFailureTestCase(
            "time zone not on 30 minute increment",
            {
                "tz": "21:12",
            },
            "Minutes portion of time zone must be 30 or 00.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_recording_date_text_parse_failure(tc: PackTextParseFailureTestCase) -> None:
    test_base.run_pack_text_parse_failure_test_case(tc, pack.VAUXRecordingDate)
