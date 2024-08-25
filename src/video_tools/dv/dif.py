"""Model classes for working with raw DIF data."""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass
from enum import IntEnum

import video_tools.dv.dif_pack as pack
import video_tools.dv.file_info as dv_file_info


# DIF block types.  Values are the three section type bits SCT2..0
class DIFBlockType(IntEnum):
    HEADER = 0x0
    SUBCODE = 0x1
    VAUX = 0x2
    AUDIO = 0x3
    VIDEO = 0x4


DIF_BLOCK_SIZE = 80

# SMPTE 306M-2002 Section 11.2 Data structure
DIF_SEQUENCE_TRANSMISSION_ORDER = list(
    itertools.chain.from_iterable(
        itertools.chain.from_iterable(
            [
                [[DIFBlockType.HEADER]],
                [[DIFBlockType.SUBCODE]] * 2,
                [[DIFBlockType.VAUX]] * 3,
                [[DIFBlockType.AUDIO], [DIFBlockType.VIDEO] * 15] * 9,
            ]
        )
    )
)


def calculate_dif_block_numbers() -> list[int]:
    block_count: dict[DIFBlockType, int] = defaultdict(int)
    block_numbers = []
    for block_index in range(len(DIF_SEQUENCE_TRANSMISSION_ORDER)):
        block_numbers.append(block_count[DIF_SEQUENCE_TRANSMISSION_ORDER[block_index]])
        block_count[DIF_SEQUENCE_TRANSMISSION_ORDER[block_index]] += 1
    return block_numbers


# Every block section type is individually indexed.
DIF_BLOCK_NUMBER = calculate_dif_block_numbers()


@dataclass(frozen=True, kw_only=True)
class FrameData:
    """Top-level class containing DV frame metadata."""

    # From DIF block headers
    arbitrary_bits: int

    # From header DIF block
    header_track_application_id: int
    header_audio_application_id: int
    header_video_application_id: int
    header_subcode_application_id: int

    # From subcode DIF block
    subcode_track_application_id: int
    subcode_subcode_application_id: int
    # indexed by: channel number, sequence number, SSYB number
    # value is always the pack header (subcode pack type) when reading a DV file.
    # it may be None when writing if we want to leave the pack unmodified.
    subcode_pack_types: list[list[list[int | None]]]
    subcode_title_timecode: pack.TitleTimecode
    subcode_smpte_binary_group: pack.SMPTEBinaryGroup
    subcode_recording_date: pack.SubcodeRecordingDate
    subcode_vaux_recording_time: pack.VAUXRecordingTime

    @property
    def system(self) -> dv_file_info.DVSystem:
        return dv_file_info.DIF_SEQUENCE_COUNT_TO_SYSTEM[len(self.subcode_pack_types[0])]
