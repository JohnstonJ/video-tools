import video_tools.dv.file_info as dv_file_info

from .base import (
    Pack,
    PackType,
)
from .date import (
    AAUXRecordingDate,
    VAUXRecordingDate,
)
from .misc import (
    AAUXBinaryGroup,
    NoInfo,
    TitleBinaryGroup,
    Unknown,
    VAUXBinaryGroup,
)
from .time import (
    AAUXRecordingTime,
    TitleTimecode,
    VAUXRecordingTime,
)


def parse_binary(pack_bytes: bytes, system: dv_file_info.DVSystem) -> Pack | None:
    """Create a new instance of a block by parsing a binary DIF block from a DV file.

    The input byte array is expected to be an 80 byte DIF block.  The output type will be
    one of the derived classes, based on the detected block type.
    """
    assert len(pack_bytes) == 5
    match pack_bytes[0]:
        case PackType.TITLE_TIMECODE:
            return TitleTimecode.parse_binary(pack_bytes, system)
        case PackType.TITLE_BINARY_GROUP:
            return TitleBinaryGroup.parse_binary(pack_bytes, system)
        case PackType.AAUX_RECORDING_DATE:
            return AAUXRecordingDate.parse_binary(pack_bytes, system)
        case PackType.AAUX_RECORDING_TIME:
            return AAUXRecordingTime.parse_binary(pack_bytes, system)
        case PackType.AAUX_BINARY_GROUP:
            return AAUXBinaryGroup.parse_binary(pack_bytes, system)
        case PackType.VAUX_RECORDING_DATE:
            return VAUXRecordingDate.parse_binary(pack_bytes, system)
        case PackType.VAUX_RECORDING_TIME:
            return VAUXRecordingTime.parse_binary(pack_bytes, system)
        case PackType.VAUX_BINARY_GROUP:
            return VAUXBinaryGroup.parse_binary(pack_bytes, system)
        case PackType.NO_INFO:
            return NoInfo.parse_binary(pack_bytes, system)
        case _:
            return Unknown.parse_binary(pack_bytes, system)
