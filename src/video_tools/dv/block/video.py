from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import video_tools.dv.file.info as dv_file_info

from .base import Block, BlockID, Type


# DIF video block
# Standards on how video data is packaged in the digital interface:
#  - IEC 61834-2:1998 Section 11.4.2 - Data part - Video section
#  - IEC 61834-2:1998 Figure 71 - Data in the video section
#  - IEC 61834-2:1998 Table B.7 - Method of transmitting and recording data of a video DIF block
#  - SMPTE 306M-2002 Section 11.2.2.5 - Video section
# Standards on the formatting of the video blocks themselves:
#  - IEC 61834-2:1998 Section 3.4 - Video sector
#  - IEC 61834-2:1998 Figure 10 - Structure of sync blocks in video sector
#  - IEC 61834-2:1998 Section 7 - Video signal processing
#  - IEC 61834-2:1998 Figure 37 - The arrangement of a compressed macro block
#  - IEC 61834-2:1998 Table 26 - Definition of STA
#  - SMPTE 306M-2002 Section 6.4 - Video sector
#  - SMPTE 306M-2002 Section 8 - Video processing
# Important notes:
#  - Each tape track physically holds 135 video blocks in a dedicated area of the tape track.
#    They are located between the VAUX blocks.
#  - Organization of video data during processing:
#    - Video data is assigned to 8x8 pixel DCT blocks (with one edge case for NTSC color channel).
#    - DCT blocks contain only Y, Cr, or Cb channel data.
#    - 6 adjacent DCT blocks are in a macro block: 4 Y, 1 Cr, 1 Cb.  For example, with one edge
#      case, NTSC will use 32x8 pixel macro blocks.
#    - 27 adjacent macro blocks are assigned to a super block.
#    - 5 macro blocks are assigned/shuffled into a video segment via some complex formula.
#    - A video segment is compressed to 385 bytes, or 77 bytes per compressed macro block - exactly
#      the size of a DIF block's data after accounting for the 3-byte DIF block ID.
#  - Every DIF block contains exactly one 77-byte compressed macro block.  There are no unused DIF
#    video blocks, so we must unconditionally process every one.
#  - The very first byte of a compressed macro block contains two nibbles: STA in the MSB, and
#    QNO in the LSB.  The remaining bytes are the 6 DCT bytes.
#    - STA is a status nibble.  Non-zero means that there is some kind of error that has happened.
#      A non-zero value here is how MediaInfoLib identifies error blocks.
#    - QNO is the quantization number applied to the macro block, and is not of interest to us for
#      identifying error blocks.
@dataclass(frozen=True, kw_only=True)
class Video(Block):
    video_data: bytes  # always 77 bytes

    def validate(self, file_info: dv_file_info.Info) -> str | None:
        assert len(self.video_data) == 77

        return None

    def has_video_errors(self) -> bool:
        return self.video_data[0] & 0xF0 != 0x00

    # Functions for going to/from binary blocks

    type: ClassVar[Type] = Type.VIDEO

    @classmethod
    def _do_parse_binary(
        cls, block_bytes: bytes, block_id: BlockID, file_info: dv_file_info.Info
    ) -> Video:
        return cls(
            block_id=block_id,
            video_data=block_bytes[3:],
        )

    def _do_to_binary(self, file_info: dv_file_info.Info) -> bytes:
        return bytes([*self.block_id.to_binary(file_info), *self.video_data])
