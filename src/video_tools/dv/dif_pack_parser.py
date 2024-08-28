import video_tools.dv.dif_pack as pack
import video_tools.dv.file_info as dv_file_info


def parse_binary(pack_bytes: bytes, system: dv_file_info.DVSystem) -> pack.Pack | None:
    """Create a new instance of a block by parsing a binary DIF block from a DV file.

    The input byte array is expected to be an 80 byte DIF block.  The output type will be
    one of the derived classes, based on the detected block type.
    """
    assert len(pack_bytes) == 5
    match pack_bytes[0]:
        case pack.PackType.TITLE_TIMECODE:
            return pack.TitleTimecode.parse_binary(pack_bytes, system)
        case pack.PackType.TITLE_BINARY_GROUP:
            return pack.TitleBinaryGroup.parse_binary(pack_bytes, system)
        case pack.PackType.AAUX_RECORDING_DATE:
            return pack.AAUXRecordingDate.parse_binary(pack_bytes, system)
        case pack.PackType.AAUX_RECORDING_TIME:
            return pack.AAUXRecordingTime.parse_binary(pack_bytes, system)
        case pack.PackType.AAUX_BINARY_GROUP:
            return pack.AAUXBinaryGroup.parse_binary(pack_bytes, system)
        case pack.PackType.VAUX_RECORDING_DATE:
            return pack.VAUXRecordingDate.parse_binary(pack_bytes, system)
        case pack.PackType.VAUX_RECORDING_TIME:
            return pack.VAUXRecordingTime.parse_binary(pack_bytes, system)
        case pack.PackType.VAUX_BINARY_GROUP:
            return pack.VAUXBinaryGroup.parse_binary(pack_bytes, system)
        case pack.PackType.NO_INFO:
            return pack.NoInfo.parse_binary(pack_bytes, system)
        case _:
            return pack.Unknown.parse_binary(pack_bytes, system)
