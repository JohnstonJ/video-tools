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
