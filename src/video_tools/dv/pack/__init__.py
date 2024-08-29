"""Contains model classes for DIF data packs contained in subcode, audio, and VAUX DIF blocks."""

from .aaux_source import (
    AAUXSource,
    AudioBlockPairing,
    AudioQuantization,
    EmphasisTimeConstant,
    LockedMode,
    StereoMode,
)
from .base import (
    CSVFieldMap,
    Pack,
    Type,
    ValidationError,
)
from .date import (
    AAUXRecordingDate,
    DaylightSavingTime,
    GenericDate,
    VAUXRecordingDate,
    Week,
)
from .misc import (
    AAUXBinaryGroup,
    GenericBinaryGroup,
    NoInfo,
    TitleBinaryGroup,
    Unknown,
    VAUXBinaryGroup,
)
from .parser import parse_binary
from .source_control import (
    CompressionCount,
    CopyProtection,
    InputSource,
    SourceSituation,
)
from .time import (
    AAUXRecordingTime,
    BlankFlag,
    ColorFrame,
    GenericTimecode,
    PolarityCorrection,
    TitleTimecode,
    VAUXRecordingTime,
)
from .vaux_source import (
    BlackAndWhiteFlag,
    ColorFramesID,
    SourceCode,
    SourceType,
    VAUXSource,
)
from .vaux_source_control import (
    FrameChange,
    FrameField,
    StillFieldPicture,
    VAUXRecordingMode,
    VAUXSourceControl,
)

__all__ = [
    "AAUXBinaryGroup",
    "AAUXRecordingDate",
    "AAUXRecordingTime",
    "AAUXSource",
    "AudioBlockPairing",
    "AudioQuantization",
    "BlackAndWhiteFlag",
    "BlankFlag",
    "ColorFrame",
    "ColorFramesID",
    "CompressionCount",
    "CopyProtection",
    "CSVFieldMap",
    "DaylightSavingTime",
    "EmphasisTimeConstant",
    "FrameChange",
    "FrameField",
    "GenericBinaryGroup",
    "GenericDate",
    "GenericTimecode",
    "InputSource",
    "LockedMode",
    "NoInfo",
    "Pack",
    "Type",
    "ValidationError",
    "parse_binary",
    "PolarityCorrection",
    "SourceCode",
    "SourceSituation",
    "SourceType",
    "StereoMode",
    "StillFieldPicture",
    "TitleBinaryGroup",
    "TitleTimecode",
    "Unknown",
    "VAUXBinaryGroup",
    "VAUXRecordingDate",
    "VAUXRecordingMode",
    "VAUXRecordingTime",
    "VAUXSource",
    "VAUXSourceControl",
    "Week",
]
