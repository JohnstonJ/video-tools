import pytest

import tests.dv.pack.test_base as test_base
import video_tools.dv.pack as pack
from tests.dv.pack.test_base import (
    PackBinaryTestCase,
    PackTextSuccessTestCase,
    PackValidateCase,
)

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
    test_base.run_pack_binary_test_case(tc, pack.TitleBinaryGroup)


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
    test_base.run_pack_binary_test_case(tc, pack.AAUXBinaryGroup)


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
    test_base.run_pack_binary_test_case(tc, pack.VAUXBinaryGroup)


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
    test_base.run_pack_validate_case(tc)


@pytest.mark.parametrize(
    "tc",
    [
        PackTextSuccessTestCase(
            "basic test",
            {None: "0x12345678"},
            pack.TitleBinaryGroup(value=bytes.fromhex("12 34 56 78")),
        ),
        PackTextSuccessTestCase(
            "empty",
            {None: ""},
            pack.TitleBinaryGroup(),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_title_binary_group_text_success(tc: PackTextSuccessTestCase) -> None:
    test_base.run_pack_text_success_test_case(tc, pack.TitleBinaryGroup)


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
    test_base.run_pack_binary_test_case(tc, pack.NoInfo)


# ======================== UNKNOWN GROUP PACK TESTS ========================


@pytest.mark.parametrize(
    "tc",
    [
        PackBinaryTestCase(
            "basic test",
            "12 34 56 78 9A",
            pack.Unknown(value=bytes.fromhex("12 34 56 78 9A")),
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_unknown_binary(tc: PackBinaryTestCase) -> None:
    test_base.run_pack_binary_test_case(tc, pack.Unknown)


@pytest.mark.parametrize(
    "tc",
    [
        PackValidateCase("no value", pack.Unknown(), "A pack value was not provided."),
        PackValidateCase(
            "wrong length",
            pack.Unknown(value=b"ab"),
            "The pack value has the wrong length: expected 5 bytes but got 2.",
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_unknown_validate(tc: PackValidateCase) -> None:
    test_base.run_pack_validate_case(tc)
