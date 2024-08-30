"""Shared types between camera DIF packs."""

from enum import IntEnum


class FocusMode(IntEnum):
    AUTOMATIC = 0x0
    MANUAL = 0x1


def __calculate_focus_positions() -> dict[int, int | None]:
    focus: dict[int, int | None] = {}
    for bits in range(0x00, 0x7E + 1):
        focus[bits] = (bits >> 2) * (10 ** (bits & 0x03))
    focus[0x7F] = None
    return focus


_focus_position_bits_to_length = __calculate_focus_positions()
_focus_position_length_to_bits = {
    ln: b for b, ln in reversed(list(_focus_position_bits_to_length.items()))
}
# NOTE: we don't expect that every calculated focus value is unique: there are multiple ways to
# represent zero.  The items list above is reversed so that LSBs are also zero when MSBs are zero.

ValidFocusPositions: list[int] = [k for k in _focus_position_length_to_bits.keys() if k is not None]
