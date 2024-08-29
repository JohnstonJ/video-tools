from dataclasses import dataclass

import pytest

import video_tools.dv.file_info as dv_file_info
import video_tools.dv.pack as pack

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


@dataclass
class PackTextSuccessTestCase:
    name: str
    input: dict[str | None, str]
    parsed: pack.Pack
    output: dict[str | None, str] | None = None


def run_pack_text_success_test_case(tc: PackTextSuccessTestCase, cls: type[pack.Pack]) -> None:
    """Test round trip of a pack from text, to parsed, and then back to text."""
    p = cls.parse_text_values(tc.input)
    assert p == tc.parsed
    output = tc.output if tc.output is not None else tc.input
    assert p.to_text_values() == output


@dataclass
class PackTextParseFailureTestCase:
    name: str
    input: dict[str | None, str]
    parse_failure: str


def run_pack_text_parse_failure_test_case(
    tc: PackTextParseFailureTestCase, cls: type[pack.Pack]
) -> None:
    """Test that a text parsing attempt will fail."""
    with pytest.raises(pack.PackValidationError, match=tc.parse_failure):
        cls.parse_text_values(tc.input)


# ======================== BASE CLASS EDGE CASE TESTING ========================
def test_base_pack_validation() -> None:
    with pytest.raises(AssertionError):
        # wrong header
        pack.NoInfo.parse_binary(bytes.fromhex("00 FF FF FF FF"), NTSC)
    with pytest.raises(AssertionError):
        # wrong length
        pack.NoInfo.parse_binary(bytes.fromhex("FF FF FF FF"), NTSC)
