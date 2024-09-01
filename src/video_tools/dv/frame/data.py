from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import video_tools.dv.block as block
import video_tools.dv.file.info as dv_file_info
import video_tools.dv.pack as pack


class FrameError(ValueError):
    pass


# IEC 61834-2:1998 Figure 65 - Transmission order of DIF blocks in a DIF sequence
# SMPTE 306M-2002 Section 11.2 Data structure
BLOCK_TRANSMISSION_ORDER: list[block.BlockType] = [
    block.BlockType.HEADER,
    *[block.BlockType.SUBCODE] * 2,
    *[block.BlockType.VAUX] * 3,
    *[block.BlockType.AUDIO, *[block.BlockType.VIDEO] * 15] * 9,
]


def _calculate_block_numbers() -> list[int]:
    block_count: dict[block.BlockType, int] = defaultdict(int)
    block_numbers = []
    for block_index in range(len(BLOCK_TRANSMISSION_ORDER)):
        block_numbers.append(block_count[BLOCK_TRANSMISSION_ORDER[block_index]])
        block_count[BLOCK_TRANSMISSION_ORDER[block_index]] += 1
    return block_numbers


# Every block section type is individually indexed.  This maps from overall position of a
# DIF block in the sequence to the DIF block number of that type.
BLOCK_NUMBER = _calculate_block_numbers()


@dataclass(frozen=True, kw_only=True)
class Data:
    """Top-level class containing consolidated data for a DV frame.

    Frame data can be written to CSV file columns, or to a binary file.  The latter requires
    audio and video data.
    """

    # ===== General information =====

    sequence: int  # from DIF BlockID

    # ===== DIF block: header data =====

    header_video_frame_dif_sequence_count: int
    header_track_pitch: block.TrackPitch | None
    header_pilot_frame: int | None
    header_application_id_track: block.ApplicationIDTrack | None
    header_application_id_1: block.ApplicationID1 | None
    header_application_id_2: block.ApplicationID2 | None
    header_application_id_3: block.ApplicationID3 | None

    # ===== DIF block: subcode data =====

    # ID parts of subcode data.  When reading, values chosen are the most commonly seen throughout
    # the frame.  None means that no subcode ID parts containing the information could be read.

    subcode_index: bool | None
    subcode_skip: bool | None
    subcode_picture: bool | None
    subcode_application_id_track: block.ApplicationIDTrack | None
    subcode_application_id_3: block.ApplicationID3 | None
    # Outer dimension is channel number.  Inner dimension is sequence/track number.
    subcode_absolute_track_numbers: list[list[int | None]]
    subcode_blank_flag: block.BlankFlag | None

    # Packs in subcode.  Since pack layout can vary widely, we store a full mapping of the entire
    # pack layout within the frame.  However, we only keep one copy of each unique pack value that
    # is expected for each pack type.  When reading a pack, the most common value is chosen.
    #
    # We also only keep copies of the pack types that are known to appear in a subcode block.  This
    # is to reduce the number of columns in the CSV file.  If other pack types are shown to appear,
    # then we can easily add them here.

    # Pack types is indexed by: channel number (1 or 2 elements), sequence/track number
    # (10 or 12 elements), sync block number (12 elements).
    subcode_pack_types: list[list[list[int]]]
    # List of pack types that are specified in IEC 61834-2:1998 Table 29 - Subcode data of the main
    # area and recommended data of the optional area for no optional use (for user's tape)
    subcode_title_timecode: pack.TitleTimecode
    subcode_title_binary_group: pack.TitleBinaryGroup
    subcode_vaux_recording_date: pack.VAUXRecordingDate
    subcode_vaux_recording_time: pack.VAUXRecordingTime
    # AAUX packs are less common, but allowed by standard:
    subcode_aaux_recording_date: pack.AAUXRecordingDate
    subcode_aaux_recording_time: pack.AAUXRecordingTime

    # ===== DIF block: VAUX data =====

    # VAUX packs are stored here very similarly to subcode packs.

    # Pack types is indexed by: channel number (1 or 2 elements), sequence/track number
    # (10 or 12 elements), sync block number (45 elements).
    vaux_pack_types: list[list[list[int]]]
    # List of pack types specified in IEC 61834-2:1998 Table 32 - VAUX data of the main area
    vaux_source: pack.VAUXSource
    vaux_source_control: pack.VAUXSourceControl
    vaux_recording_date: pack.VAUXRecordingDate
    vaux_recording_time: pack.VAUXRecordingTime
    vaux_binary_group: pack.VAUXBinaryGroup
    vaux_camera_consumer_1: pack.CameraConsumer1
    vaux_camera_consumer_2: pack.CameraConsumer2
    vaux_camera_shutter: pack.CameraShutter

    # ===== DIF block: audio data =====

    # AAUX packs are stored here very similarly to subcode packs.

    # Pack types is indexed by: DIF channel number (1 or 2 elements), sequence/track number
    # (10 or 12 elements), sync block number (9 elements).
    aaux_pack_types: list[list[list[int]]]
    # List of pack types specified in IEC 61834-2:1998 Table 31 - AAUX data of the main area.
    # Remember that multi-channel audio is stored in a series of 5 or 6 track audio blocks.
    # Therefore, all packs are first indexed by DIF channel (1 or 2 elements), followed by audio
    # block number (2 elements)... unless we expect the pack to be the same across all audio blocks.
    aaux_source: list[list[pack.AAUXSource]]
    aaux_source_control: list[list[pack.AAUXSourceControl]]
    # It's theoretically possible that different audio blocks could have different recording times:
    aaux_recording_date: list[list[pack.AAUXRecordingDate]]
    aaux_recording_time: list[list[pack.AAUXRecordingTime]]
    aaux_binary_group: list[list[pack.AAUXBinaryGroup]]

    # Audio samples / data

    # Audio data is indexed by: DIF channel number (1 or 2 elements), sequence/track number
    # (10 or 12 elements), sync block number (9 elements).
    audio_data: list[list[list[bytes]]] | None
    # Whether the corresponding block has errors in it:
    audio_data_errors: list[list[list[bool]]] | None
    # Proportion [0.0, 1.0] of audio blocks that had error.  This is indexed by channel (1 or 2
    # elements) and audio block number (2 elements):
    audio_data_error_summary: list[list[float]]

    # ===== DIF block: video data =====

    # Video data is indexed by: DIF channel number (1 or 2 elements), sequence/track number
    # (10 or 12 elements), sync block number (135 elements).
    video_data: list[list[list[bytes]]] | None
    # whether the corresponding data has (potentially concealed) errors in it
    video_data_errors: list[list[list[bool]]] | None
    # Proportion [0.0, 1.0] of video blocks that had errors:
    video_data_error_summary: float

    # ===== Validation functions =====

    def validate(self, file_info: dv_file_info.Info) -> None:
        # Detailed data validation is done inside of the blocks.  Here we mainly focus on array
        # lengths.

        # Check all arrays indexed by channel, sequence, maybe block
        channels = file_info.video_frame_channel_count
        sequences = file_info.video_frame_dif_sequence_count
        assert len(self.subcode_absolute_track_numbers) == channels
        assert len(self.subcode_pack_types) == channels
        assert len(self.vaux_pack_types) == channels
        assert len(self.aaux_pack_types) == channels
        # audio blocks/packs:
        assert len(self.aaux_source) == channels
        assert len(self.aaux_source_control) == channels
        assert len(self.aaux_recording_date) == channels
        assert len(self.aaux_recording_time) == channels
        assert len(self.aaux_binary_group) == channels
        # audio/video data:
        assert self.audio_data is None or len(self.audio_data) == channels
        assert self.audio_data_errors is None or len(self.audio_data_errors) == channels
        assert len(self.audio_data_error_summary) == channels
        assert self.video_data is None or len(self.video_data) == channels
        assert self.video_data_errors is None or len(self.video_data_errors) == channels
        for channel in range(file_info.video_frame_channel_count):
            assert len(self.subcode_absolute_track_numbers[channel]) == sequences
            assert len(self.subcode_pack_types[channel]) == sequences
            assert len(self.vaux_pack_types[channel]) == sequences
            assert len(self.aaux_pack_types[channel]) == sequences
            # audio blocks/packs:
            assert len(self.aaux_source[channel]) == 2
            assert len(self.aaux_source_control[channel]) == 2
            assert len(self.aaux_recording_date[channel]) == 2
            assert len(self.aaux_recording_time[channel]) == 2
            assert len(self.aaux_binary_group[channel]) == 2
            # audio/video data:
            assert self.audio_data is None or len(self.audio_data[channel]) == sequences
            assert (
                self.audio_data_errors is None or len(self.audio_data_errors[channel]) == sequences
            )
            assert len(self.audio_data_error_summary[channel]) == 2
            assert self.video_data is None or len(self.video_data[channel]) == sequences
            assert (
                self.video_data_errors is None or len(self.video_data_errors[channel]) == sequences
            )
            for sequence in range(sequences):
                assert len(self.subcode_pack_types[channel][sequence]) == 12
                assert len(self.vaux_pack_types[channel][sequence]) == 45
                assert len(self.aaux_pack_types[channel][sequence]) == 9
                # audio/video data:
                assert self.audio_data is None or len(self.audio_data[channel][sequence]) == 9
                assert (
                    self.audio_data_errors is None
                    or len(self.audio_data_errors[channel][sequence]) == 9
                )
                assert self.video_data is None or len(self.video_data[channel][sequence]) == 135
                assert (
                    self.video_data_errors is None
                    or len(self.video_data_errors[channel][sequence]) == 135
                )
