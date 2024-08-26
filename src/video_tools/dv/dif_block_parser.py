import video_tools.dv.dif_block as block
import video_tools.dv.dif_block_header as block_header
import video_tools.dv.file_info as dv_file_info


def parse_binary(block_bytes: bytes, system: dv_file_info.DVSystem) -> block.Block:
    """Create a new instance of a block by parsing a binary DIF block from a DV file.

    The input byte array is expected to be an 80 byte DIF block.  The output type will be
    one of the derived classes, based on the detected block type.
    """
    assert len(block_bytes) == block.DIF_BLOCK_SIZE
    id = block.BlockID.parse_binary(block_bytes[0:3], system)
    match id.type:
        case block.BlockType.HEADER:
            return block_header.Header.parse_binary(block_bytes, system)
        case _:
            assert False
