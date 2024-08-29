"""Shared types between source control DIF packs."""

from enum import IntEnum


class CopyProtection(IntEnum):
    NO_RESTRICTION = 0x0
    RESERVED = 0x1
    ONE_GENERATION_ONLY = 0x2
    NOT_PERMITTED = 0x3


class InputSource(IntEnum):
    ANALOG = 0x0
    DIGITAL = 0x1
    RESERVED = 0x2


class CompressionCount(IntEnum):
    CMP_1 = 0x0
    CMP_2 = 0x1
    CMP_3_OR_MORE = 0x2


class SourceSituation(IntEnum):
    SCRAMBLED_SOURCE_WITH_AUDIENCE_RESTRICTIONS = 0x0
    SCRAMBLED_SOURCE_WITHOUT_AUDIENCE_RESTRICTIONS = 0x1
    SOURCE_WITH_AUDIENCE_RESTRICTIONS = 0x2
