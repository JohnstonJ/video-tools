from dataclasses import dataclass

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


def run_pack_binary_test_case(tc: PackBinaryTestCase, cls: type[pack.Pack]) -> None:
    """Test round trip of a pack from binary, to parsed, and then back to binary."""
    input = bytes.fromhex(tc.input)
    p = cls.parse_binary(input, NTSC)
    assert p == tc.parsed
    if p:
        output = bytes.fromhex(tc.output) if tc.output is not None else input
        assert p.to_binary(NTSC) == output


@dataclass
class PackValidateCase:
    name: str
    input: pack.Pack
    failure: str


def run_pack_validate_case(tc: PackValidateCase) -> None:
    """Test validation failures when writing a pack to binary."""
    with pytest.raises(pack.PackValidationError, match=tc.failure):
        tc.input.to_binary(NTSC)


# ======================== BASE CLASS EDGE CASE TESTING ========================
def test_base_pack_validation() -> None:
    with pytest.raises(AssertionError):
        # wrong header
        pack.NoInfo.parse_binary(bytes.fromhex("00 FF FF FF FF"), NTSC)
    with pytest.raises(AssertionError):
        # wrong length
        pack.NoInfo.parse_binary(bytes.fromhex("FF FF FF FF"), NTSC)


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
