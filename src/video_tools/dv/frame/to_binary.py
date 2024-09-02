"""Functions for writing binary frames."""

from __future__ import annotations

import video_tools.dv.block as block
import video_tools.dv.data_util as du
import video_tools.dv.file.info as dv_file_info
import video_tools.dv.pack as pack

from .data import BLOCK_NUMBER, BLOCK_TRANSMISSION_ORDER, Data, FrameError


def to_binary(frame: Data, file_info: dv_file_info.Info) -> bytes:
    frame_bytes = bytearray(file_info.video_frame_size)
    b_start = 0  # current block starting position

    for channel in range(file_info.video_frame_channel_count):
        for sequence in range(file_info.video_frame_dif_sequence_count):
            for blk in range(len(BLOCK_TRANSMISSION_ORDER)):
                # Parse the block
                try:
                    frame_bytes[b_start : b_start + block.BLOCK_SIZE] = _to_binary_block(
                        frame,
                        channel,
                        sequence,
                        blk,
                        file_info,
                    )
                except Exception as e:
                    raise FrameError(
                        f"Error while outputting binary data for channel {channel}, "
                        f"DIF sequence/track {sequence}, block {blk}."
                    ) from e

                b_start += block.BLOCK_SIZE

    assert b_start == len(frame_bytes)
    return frame_bytes


def _to_binary_block(
    frame: Data,
    channel: int,
    sequence: int,
    blk: int,  # overall block number within the DIF sequence (not numbered by block type)
    file_info: dv_file_info.Info,
) -> bytes:
    block_type = BLOCK_TRANSMISSION_ORDER[blk]
    block_number = BLOCK_NUMBER[blk]

    block_id = block.BlockID(
        type=block_type,
        sequence=(
            0xF
            if block_type == block.BlockType.HEADER or block_type == block.BlockType.SUBCODE
            else frame.sequence
        ),
        channel=channel,
        dif_sequence=sequence,
        dif_block=block_number,
    )

    blk_data: block.Block
    pack_data: list[pack.Pack | None]
    if block_type == block.BlockType.HEADER:
        blk_data = block.Header(
            block_id=block_id,
            video_frame_dif_sequence_count=frame.header_video_frame_dif_sequence_count,
            track_pitch=frame.header_track_pitch,
            pilot_frame=frame.header_pilot_frame,
            application_id_track=frame.header_application_id_track,
            application_id_1=frame.header_application_id_1,
            application_id_2=frame.header_application_id_2,
            application_id_3=frame.header_application_id_3,
        )
    elif block_type == block.BlockType.SUBCODE:
        # build ID parts of subcode block
        tag_element_count = 5 if block_number == 0 else 4
        index = [frame.subcode_index] * tag_element_count
        skip = [frame.subcode_skip] * tag_element_count
        picture = [frame.subcode_picture] * tag_element_count
        application_id_track = frame.subcode_application_id_track
        application_id_3 = frame.subcode_application_id_3
        blank_flag = [frame.subcode_blank_flag] * 2

        # build final absolute track number
        abst = frame.subcode_absolute_track_numbers[channel][sequence]
        abst_parts: list[list[int | None]]
        if abst is not None:
            abst_parts = [
                [abst & 0x7F] * 2,
                [((abst << 1) & 0x00FF00) >> 8] * 2,
                [((abst << 1) & 0xFF0000) >> 16] * 2,
            ]
        else:
            abst_parts = [[None] * 2] * 3

        # Delete all parts of a subcode ID part if any part if it is missing.  This will ensure
        # that the Subcode block writes out an invalid sync block number, and thus ensure no
        # realistic chance that data in this ID part is misinterpreted as valid.  Note that
        # Subcode also has a validation that will catch this if we don't do it here.  In such a
        # scenario, the end user really should be repairing the subcode ID parts of frame data
        # before writing out to a new DV file.
        for sync_block_number in range(6):
            # Detect if any part is missing in this sync block
            # The logic here is similar to Subcode.validate
            any_missing = False
            if sync_block_number == 0:
                any_missing = any_missing or application_id_3 is None
            elif block_number == 1 and sync_block_number == 5:
                any_missing = any_missing or application_id_track is None
            else:
                tag_index = sync_block_number - 1
                any_missing = (
                    any_missing
                    or index[tag_index] is None
                    or skip[tag_index] is None
                    or picture[tag_index] is None
                )

            abst_part_num = sync_block_number % 3
            abst_copy_num = int(sync_block_number / 3)
            any_missing = any_missing or abst_parts[abst_part_num][abst_copy_num] is None
            if abst_part_num == 0:
                any_missing = any_missing or blank_flag[abst_copy_num] is None

            # Delete the whole ID block parts if any part was missing
            if any_missing:
                if sync_block_number == 0:
                    application_id_3 = None
                elif block_number == 1 and sync_block_number == 5:
                    application_id_track = None
                else:
                    tag_index = sync_block_number - 1
                    index[tag_index] = None
                    skip[tag_index] = None
                    picture[tag_index] = None
                abst_parts[abst_part_num][abst_copy_num] = None
                if abst_part_num == 0:
                    blank_flag[abst_copy_num] = None

        # write the packs
        pack_types = frame.subcode_pack_types[channel][sequence][
            6 * block_number : 6 * block_number + 6
        ]
        pack_data = [
            _select_pack(frame, channel, sequence, block_type, pack_type, file_info)
            for pack_type in pack_types
        ]

        blk_data = block.Subcode(
            # ID part
            block_id=block_id,
            index=index,
            skip=skip,
            picture=picture,
            application_id_track=application_id_track,
            application_id_3=application_id_3,
            absolute_track_number_2=abst_parts[2],
            absolute_track_number_1=abst_parts[1],
            absolute_track_number_0=abst_parts[0],
            blank_flag=blank_flag,
            # Pack part
            packs=pack_data,
            pack_types=pack_types,
        )
    elif block_type == block.BlockType.VAUX:
        pack_types = frame.vaux_pack_types[channel][sequence][
            15 * block_number : 15 * block_number + 15
        ]
        pack_data = [
            _select_pack(frame, channel, sequence, block_type, pack_type, file_info)
            for pack_type in pack_types
        ]
        blk_data = block.VAUX(
            block_id=block_id,
            packs=pack_data,
            pack_types=pack_types,
        )
    elif block_type == block.BlockType.AUDIO:
        if frame.audio_data is None:
            raise FrameError("Audio data is missing.")
        pack_type = frame.aaux_pack_types[channel][sequence][block_number]
        pack_data_single = _select_pack(frame, channel, sequence, block_type, pack_type, file_info)
        blk_data = block.Audio(
            block_id=block_id,
            pack_data=pack_data_single,
            pack_type=pack_type,
            audio_data=frame.audio_data[channel][sequence][block_number],
        )
    elif block_type == block.BlockType.VIDEO:
        if frame.video_data is None:
            raise FrameError("Audio data is missing.")
        blk_data = block.Video(
            block_id=block_id,
            video_data=frame.video_data[channel][sequence][block_number],
        )
    else:
        assert False
    return blk_data.to_binary(file_info)


def _select_pack(
    frame: Data,
    channel: int,
    sequence: int,
    block_type: block.BlockType,
    pack_type: int,
    file_info: dv_file_info.Info,
) -> pack.Pack:
    pte = pack.Type(pack_type) if pack_type in pack.Type else None
    if pte == pack.Type.NO_INFO:
        return pack.NoInfo()

    if block_type == block.BlockType.SUBCODE:
        if pte == pack.Type.TITLE_TIMECODE:
            return frame.subcode_title_timecode
        elif pte == pack.Type.TITLE_BINARY_GROUP:
            return frame.subcode_title_binary_group
        elif pte == pack.Type.VAUX_RECORDING_DATE:
            return frame.subcode_vaux_recording_date
        elif pte == pack.Type.VAUX_RECORDING_TIME:
            return frame.subcode_vaux_recording_time
        elif pte == pack.Type.AAUX_RECORDING_DATE:
            return frame.subcode_aaux_recording_date
        elif pte == pack.Type.AAUX_RECORDING_TIME:
            return frame.subcode_aaux_recording_time

    elif block_type == block.BlockType.VAUX:
        if pte == pack.Type.VAUX_SOURCE:
            return frame.vaux_source
        elif pte == pack.Type.VAUX_SOURCE_CONTROL:
            return frame.vaux_source_control
        elif pte == pack.Type.VAUX_RECORDING_DATE:
            return frame.vaux_recording_date
        elif pte == pack.Type.VAUX_RECORDING_TIME:
            return frame.vaux_recording_time
        elif pte == pack.Type.VAUX_BINARY_GROUP:
            return frame.vaux_binary_group
        elif pte == pack.Type.CAMERA_CONSUMER_1:
            return frame.vaux_camera_consumer_1
        elif pte == pack.Type.CAMERA_CONSUMER_2:
            return frame.vaux_camera_consumer_2
        elif pte == pack.Type.CAMERA_SHUTTER:
            return frame.vaux_camera_shutter

    elif block_type == block.BlockType.AUDIO:
        audio_block = int(sequence / int(file_info.video_frame_dif_sequence_count / 2))
        if pte == pack.Type.AAUX_SOURCE:
            return frame.aaux_source[channel][audio_block]
        elif pte == pack.Type.AAUX_SOURCE_CONTROL:
            return frame.aaux_source_control[channel][audio_block]
        elif pte == pack.Type.AAUX_RECORDING_DATE:
            return frame.aaux_recording_date[channel][audio_block]
        elif pte == pack.Type.AAUX_RECORDING_TIME:
            return frame.aaux_recording_time[channel][audio_block]
        elif pte == pack.Type.AAUX_BINARY_GROUP:
            return frame.aaux_binary_group[channel][audio_block]

    raise FrameError(
        f"Pack type {du.hex_int(pack_type, 2)} is not currently "
        f"supported by this tool in block type {block_type.name}."
    )
