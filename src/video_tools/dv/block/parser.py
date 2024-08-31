import video_tools.dv.file.info as dv_file_info

from .audio import Audio
from .base import BLOCK_SIZE, Block, BlockID, BlockType
from .header import Header
from .subcode import Subcode
from .vaux import VAUX
from .video import Video


def parse_binary(block_bytes: bytes, file_info: dv_file_info.Info) -> Block:
    """Create a new instance of a block by parsing a binary DIF block from a DV file.

    The input byte array is expected to be an 80 byte DIF block.  The output type will be
    one of the derived classes, based on the detected block type.
    """
    assert len(block_bytes) == BLOCK_SIZE
    id = BlockID.parse_binary(block_bytes[0:3], file_info)
    match id.type:
        case BlockType.HEADER:
            return Header.parse_binary(block_bytes, file_info)
        case BlockType.SUBCODE:
            return Subcode.parse_binary(block_bytes, file_info)
        case BlockType.VAUX:
            return VAUX.parse_binary(block_bytes, file_info)
        case BlockType.AUDIO:
            return Audio.parse_binary(block_bytes, file_info)
        case BlockType.VIDEO:
            return Video.parse_binary(block_bytes, file_info)
        case _:
            assert False
