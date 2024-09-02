from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import ClassVar, cast

import video_tools.dv.file.info as dv_file_info
import video_tools.dv.pack as pack

from .base import Block, BlockError, BlockID, Type


# DIF VAUX block
# Standards on how VAUX data is packaged in the digital interface:
#  - IEC 61834-2:1998 Section 11.4.2 - Data part - VAUX section
#  - IEC 61834-2:1998 Figure 69 - Data in the VAUX section
#  - IEC 61834-2:1998 Table 41 - DIF blocks and VAUX data-sync blocks
#  - IEC 61834-2:1998 Table B.5 - Method of transmitting and recording data of VAUX DIF block
#  - SMPTE 306M-2002 Section 11.2.2.3 - VAUX section
# Standards on the formatting of the VAUX blocks themselves:
#  - IEC 61834-2:1998 Section 3.4 - Video sector
#  - IEC 61834-2:1998 Figure 10 - Structure of sync blocks in video sector
#  - IEC 61834-2:1998 Section 7.11 - Video auxiliary data (VAUX)
#  - IEC 61834-2:1998 Section 9.3 - Main area and optional area
#  - IEC 61834-2:1998 Section 9.5 - VAUX (System data)
#  - IEC 61834-2:1998 Figure 50 - Arrangement of VAUX packs in VAUX sync blocks
#  - IEC 61834-2:1998 Table 32 - VAUX data of the main area
#  - IEC 61834-4:1998 - entire standard
#  - SMPTE 306M-2002 Section 6.4.3.4 - Composed video data
#  - SMPTE 306M-2002 Section 8.9 - Video auxiliary data (VAUX)
# Important notes:
#  - Each tape track physically holds 3 VAUX blocks ----> 3 VAUX blocks in a DIF sequence.  They
#    are embedded within the larger video sector of the tape track as a whole: extracting these
#    into a separate part of the digital interface is purely a convenience for DIF.  Physically,
#    all regular video data blocks are sandwiched between VAUX blocks within the video sector.
#  - Each DIF block holds 15 5-byte packs.  The trailing 2 block bytes are reserved (0xFF).
#  - IEC 61834-2:1998 Figure 50 is the most important reference to look at for data layout.
#  - IEC 61834-2:1998 Figure 32 shows the most important standardized required and optional packs,
#    and their positions.
#  - VAUX SOURCE and VAUX SOURCE CONTROL packs are supposed to stay the same within a video frame.
#  - Error handling:
#    - Individual packs are supposed to be turned into NO INFO packs if errors are detected within
#      any one pack of VAUX.  Presumably this means a single DIF block could have packs eliminated
#      on a pack-granular level, rather than the DIF block being read as an all-or-nothing affair.
#    - The last two reserved bytes in a DIF block are also played back as they are.
#    - All data is protected by separate error correction codes (not transmitted over DIF).  But,
#      staying defensive against bad data in the middle of a pack still seems like a good idea.
#  - In summary: the most likely scenario is that the packs are completely missing, but we should
#    still protect against bad data mid-pack by validating the packs.
@dataclass(frozen=True, kw_only=True)
class VAUX(Block):
    # The various standards prescribe various packs that are required to go in certain positions,
    # and other areas that are reserved or optional.  In practice, we will be flexible when
    # parsing and writing, and allow any pack to appear in any position.

    # Parsed pack; will be None if there is a pack parse error due to tape errors.
    packs: list[pack.Pack | None]  # 15 per DIF block; None if there is a parse error
    # List of pack type header values: this is purely informational when reading, and is not used
    # at all when writing VAUX blocks back out to binary.  It's useful to know what pack type
    # failed to be read if the above packs[n] element is None.
    pack_types: list[int]  # 15 per DIF block

    def validate(self, file_info: dv_file_info.Info) -> str | None:
        assert len(self.packs) == 15
        assert len(self.pack_types) == 15

        return None

    # Functions for going to/from binary blocks

    type: ClassVar[Type] = Type.VAUX

    @classmethod
    def _do_parse_binary(
        cls, block_bytes: bytes, block_id: BlockID, file_info: dv_file_info.Info
    ) -> VAUX:
        bin = _BinaryFields.from_buffer_copy(block_bytes[3:])

        # Quick check on the trailing reserved bits, just to minimize risk that this is real data
        # from a different standard that we don't support.  If there's a tape dropout, these bits
        # should still be 0xFF due to the underlying error detection codes.
        if any(r != 0xFF for r in bin.reserved):
            raise BlockError("Reserved bits in DIF VAUX block are unexpectedly in use.")

        return cls(
            block_id=block_id,
            packs=[
                pack.parse_binary(pack_bytes.data, file_info.system) for pack_bytes in bin.packs
            ],
            pack_types=[pack_bytes.data[0] for pack_bytes in bin.packs],
        )

    def _do_to_binary(self, file_info: dv_file_info.Info) -> bytes:
        bin = _BinaryFields(
            packs=(_Pack * 15)(
                *[
                    _Pack(
                        data=(ctypes.c_uint8 * 5)(
                            *(
                                cast(pack.Pack, self.packs[pack_number]).to_binary(file_info.system)
                                if self.packs[pack_number] is not None
                                # Send a NO INFO pack if we are missing a pack (e.g. from a previous
                                # read error).
                                else pack.NoInfo().to_binary(file_info.system)
                            )
                        ),
                    )
                    for pack_number in range(15)
                ]
            ),
            reserved=(ctypes.c_uint8 * 2)(*[0xFF] * 2),
        )
        return bytes([*self.block_id.to_binary(file_info), *bytes(bin)])


class _Pack(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("data", ctypes.c_uint8 * 5),
    ]


class _BinaryFields(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("packs", _Pack * 15),
        ("reserved", ctypes.c_uint8 * 2),
    ]
