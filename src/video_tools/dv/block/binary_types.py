import ctypes
from typing import ClassVar


class _BlockIDBinaryFields(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("sct", ctypes.c_uint8, 3),
        ("reserved_0", ctypes.c_uint8, 1),
        ("seq", ctypes.c_uint8, 4),
        ("dseq", ctypes.c_uint8, 4),
        ("fsc", ctypes.c_uint8, 1),
        ("reserved_1", ctypes.c_uint8, 3),
        ("dbn", ctypes.c_uint8, 8),
    ]


class _HeaderBinaryFields(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("dsf", ctypes.c_uint8, 1),
        ("zero", ctypes.c_uint8, 1),
        ("reserved_0", ctypes.c_uint8, 6),
        ("dftia", ctypes.c_uint8, 4),
        ("reserved_1", ctypes.c_uint8, 1),
        ("apt", ctypes.c_uint8, 3),
        ("tf1", ctypes.c_uint8, 1),
        ("reserved_2", ctypes.c_uint8, 4),
        ("ap1", ctypes.c_uint8, 3),
        ("tf2", ctypes.c_uint8, 1),
        ("reserved_3", ctypes.c_uint8, 4),
        ("ap2", ctypes.c_uint8, 3),
        ("tf3", ctypes.c_uint8, 1),
        ("reserved_4", ctypes.c_uint8, 4),
        ("ap3", ctypes.c_uint8, 3),
        ("reserved_end", ctypes.c_uint8 * 72),
    ]


class _SubcodeID0PartWithTag(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("fr", ctypes.c_uint8, 1),  # first half ID: 1 for first half, 0 for second
        ("index", ctypes.c_uint8, 1),
        ("skip", ctypes.c_uint8, 1),
        ("pp", ctypes.c_uint8, 1),
        ("abst", ctypes.c_uint8, 4),
    ]


class _SubcodeID0PartWithApplicationID(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("fr", ctypes.c_uint8, 1),  # first half ID: 1 for first half, 0 for second
        ("application_id", ctypes.c_uint8, 3),
        ("abst", ctypes.c_uint8, 4),
    ]


class _SubcodeID0Part(ctypes.BigEndianUnion):
    _pack_ = 1
    _fields_: ClassVar = [
        ("with_tag", _SubcodeID0PartWithTag),
        ("with_application_id", _SubcodeID0PartWithApplicationID),
    ]


class _SubcodeID1PartWithBF(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("abst", ctypes.c_uint8, 3),
        ("bf", ctypes.c_uint8, 1),
        ("syb", ctypes.c_uint8, 4),
    ]


class _SubcodeID1PartWithoutBF(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("abst", ctypes.c_uint8, 4),
        ("syb", ctypes.c_uint8, 4),
    ]


class _SubcodeID1Part(ctypes.BigEndianUnion):
    _pack_ = 1
    _fields_: ClassVar = [
        ("with_bf", _SubcodeID1PartWithBF),
        ("without_bf", _SubcodeID1PartWithoutBF),
    ]


class _SubcodeIDPart(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("id0", _SubcodeID0Part),
        ("id1", _SubcodeID1Part),
        ("parity", ctypes.c_uint8, 8),  # always 0xFF over digital interface
    ]


class _SubcodeSyncBlock(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("id", _SubcodeIDPart),
        ("data", ctypes.c_uint8 * 5),
    ]


class _SubcodeBinaryFields(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("sync_blocks", _SubcodeSyncBlock * 6),
        ("reserved", ctypes.c_uint8 * 29),
    ]


class _VAUXPack(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("data", ctypes.c_uint8 * 5),
    ]


class _VAUXBinaryFields(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("packs", _VAUXPack * 15),
        ("reserved", ctypes.c_uint8 * 2),
    ]


class _AudioBinaryFields(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("pack", ctypes.c_uint8 * 5),
        ("data", ctypes.c_uint8 * 72),
    ]
