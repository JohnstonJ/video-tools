"""Classes for parsing DV DIF blocks."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar

import video_tools.dv.data_util as du
import video_tools.dv.file_info as dv_file_info


class DIFBlockError(ValueError):
    pass


# General comment about the accuracy / reliability of block data:  some fields are read from the
# tape and could be corrupted from read errors from the tape.  Other fields are created by the
# tape deck's digital interface, don't physically exist on tape, and thus shouldn't generally be
# expected to have errors, assuming the FireWire interface is working correctly, and the stored
# file wasn't tampered with.  In the latter case, we have assertions to enforce consistency of
# data while reading the file, but we don't have any code / features for repairing errors, because
# none are expected in practice.  Details of this is described in IEC 61834-2:1998 Annex B.


# DIF block types.  Values are the three section type bits SCT2..0
# SMPTE 306M-2002 Section 11.2.1 ID / Table 52 - DIF block type
# IEC 61834-2:1998 Section 11.4.1 ID part / Table 36 - DIF block type
class BlockType(IntEnum):
    HEADER = 0x0
    SUBCODE = 0x1
    VAUX = 0x2
    AUDIO = 0x3
    VIDEO = 0x4
    # The remaining bit values are reserved, and we're unlikely to ever see them.


# Common DIF block ID which is at the start of every DIF block.
# SMPTE 306M-2002 Section 11.2.1 ID / Table 51 - ID data in a DIF block
# IEC 61834-2:1998 Section 11.4.1 ID part / Figure 66 - ID data in a DIF block
@dataclass
class BlockID:
    # This value is synthesized by the digital interface and should always be accurate.
    type: BlockType

    # Sequence number in IEC 61834-2; arbitrary bits in SMPTE 306M
    #  - IEC 61834-2:1998 Section 3.3.3 ID part (Audio sector).
    #  - IEC 61834-2:1998 Section 3.4.3 ID part (Video sector).
    #  - IEC 61834-2:1998 Section 3.5.3 ID part (Subcode sector).
    #  - IEC 61834-2:1998 Tables 5 / 6 - Sequence number (525-60 and 625-50 systems)
    # Important notes:
    #  - The same value is kept throughout an entire frame.
    #  - Valid values are [0x0, 0xB] for both 525-60 and 625-50 systems, and are read from the tape.
    #    There could be read errors from tape.
    #  - Exception: Header and subcode DIF blocks must have sequence values of 0xF.  This value
    #    is reliably provided by the tape deck's digital interface.
    #  - Exception: A value of 0xF shall be used if there is trouble reading from tape.
    sequence: int

    # Channel number the DIF block appears in
    # Important notes:
    #  - IEC 61834-2:1998 Figure 66 specifies that the value is always to be 0.
    #  - SMPTE 306M-2002 Table 51 specifies that the value is the channel number (0 or 1).
    #  - We can reasonably assume it is not stored on tape / is exclusive to the digital
    #    interface.  Errors are not expected.
    channel: int

    # DIF sequence number in IEC 61834-2 and SMPTE 306M
    #  - IEC 61834-2:1998 Tables 37 / 38 - DIF sequence number (525-60 and 625-50 systems)
    #  - SMPTE 306M-2002 Tables 53 / 54 - DIF sequence number (525-60 and 625-50 systems)
    # Important notes:
    #  - Range is [0, 9] for 525-60 system (NTSC), and [0, 11] for 625-50 system (PAL/SECAM).
    #  - Not stored on tape / is exclusive to the digital interface.  Errors are not expected.
    dif_sequence: int

    # DIF block number in IEC 61834-2 and SMPTE 306M
    #  - IEC 61834-2:1998 Section 11.3 - DIF sequence
    #  - SMPTE 306M-2002 Table 55 - DIF block number
    # Important notes:
    #  - The indexing is of only this block type within a single sequence.  That is, each block
    #    type is numbered independently.  The maximum values are 0 for header block, 1 for subcode
    #    block, 2 for VAUX, 8 for audio, and 134 for video.
    #  - Not stored on tape / is exclusive to the digital interface.  Errors are not expected.
    dif_block: int

    class _BinaryFields(ctypes.BigEndianStructure):
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

    __max_dbn: ClassVar[dict[BlockType, int]] = {
        BlockType.HEADER: 0,
        BlockType.SUBCODE: 1,
        BlockType.VAUX: 2,
        BlockType.AUDIO: 8,
        BlockType.VIDEO: 134,
    }

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if (
            self.type == BlockType.HEADER or self.type == BlockType.SUBCODE
        ) and self.sequence != 0xF:
            return (
                "DIF block ID for header or subcode block has unexpected "
                f"non-0xF sequence number of {du.hex_int(self.sequence, 1)}."
            )

        if (system == dv_file_info.DVSystem.SYS_525_60 and self.dif_sequence >= 10) or (
            system == dv_file_info.DVSystem.SYS_625_50 and self.dif_sequence >= 12
        ):
            return (
                f"DIF block ID has DIF sequence number of {self.dif_sequence} that "
                f"is too high for system {system.name}."
            )

        if self.dif_block > self.__max_dbn[self.type]:
            return (
                f"DIF block ID has DIF block number of {self.dif_block} that "
                f"is too high for a block type of {self.type.name}."
            )

        return None

    @classmethod
    def parse_binary(cls, id_bytes: bytes, system: dv_file_info.DVSystem) -> BlockID:
        assert len(id_bytes) == 3
        bin = cls._BinaryFields.from_buffer_copy(id_bytes)

        type = BlockType(bin.sct)

        # If this is triggered, we should look into what we're dealing with.
        if bin.reserved_0 != 0x1 or bin.reserved_1 != 0x7:
            raise DIFBlockError("Reserved bits in DIF block identifier were unexpectedly cleared.")

        id = BlockID(
            type=type,
            sequence=bin.seq,
            channel=bin.fsc,
            dif_sequence=bin.dseq,
            dif_block=bin.dbn,
        )
        validation_message = id.validate(system)
        if validation_message is not None:
            raise DIFBlockError(validation_message)
        return id

    def to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        validation_message = self.validate(system)
        if validation_message is not None:
            raise DIFBlockError(validation_message)

        bin = self._BinaryFields(
            sct=int(self.type),
            reserved_0=0x1,
            seq=int(self.sequence),
            dseq=int(self.dif_sequence),
            fsc=int(self.channel),
            reserved_1=0x7,
            dbn=int(self.dif_block),
        )
        return bytes(bin)
