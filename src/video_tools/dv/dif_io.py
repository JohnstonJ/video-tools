"""Contains high-level functions for reading and modifying DIF blocks in a DV file."""

from collections import defaultdict
from typing import BinaryIO, cast

import video_tools.dv.dif as dif
import video_tools.dv.dif_pack as pack
import video_tools.io_util as io_util
from video_tools.dv.file_info import DVFileInfo


def read_frame_data(frame_bytes: bytearray, file_info: DVFileInfo) -> dif.FrameData:
    b_start = 0  # current block starting position

    # DIF block header
    arbitrary_bits_hist: dict[int, int] = defaultdict(int)

    # Header DIF block info
    header_track_application_id_hist: dict[int, int] = defaultdict(int)
    header_audio_application_id_hist: dict[int, int] = defaultdict(int)
    header_video_application_id_hist: dict[int, int] = defaultdict(int)
    header_subcode_application_id_hist: dict[int, int] = defaultdict(int)

    # Subcode DIF block info
    subcode_track_application_id_hist: dict[int, int] = defaultdict(int)
    subcode_subcode_application_id_hist: dict[int, int] = defaultdict(int)
    subcode_pack_types: list[list[list[int | None]]] = [
        [
            [None for ssyb in range(12)]
            for sequence in range(file_info.video_frame_dif_sequence_count)
        ]
        for channel in range(file_info.video_frame_channel_count)
    ]
    subcode_title_timecode_hist: dict[pack.TitleTimecode, int] = defaultdict(int)
    subcode_title_binary_group_hist: dict[pack.TitleBinaryGroup, int] = defaultdict(int)
    subcode_vaux_recording_date_hist: dict[pack.VAUXRecordingDate, int] = defaultdict(int)
    subcode_vaux_recording_time_hist: dict[pack.VAUXRecordingTime, int] = defaultdict(int)

    for channel in range(file_info.video_frame_channel_count):
        for sequence in range(file_info.video_frame_dif_sequence_count):
            ssyb_bytes = []  # subcode bytes seen in sequence
            for block in range(len(dif.DIF_SEQUENCE_TRANSMISSION_ORDER)):
                # Read DIF block header
                # SMPTE 306M-2002 Section 11.2.1 ID
                section_type = frame_bytes[b_start] >> 5
                arbitrary_bits = frame_bytes[b_start] & 0x0F
                dif_sequence_number = (frame_bytes[b_start + 1] & 0xF0) >> 4
                fsc = (frame_bytes[b_start + 1] & 0x08) >> 4
                dif_block_number = frame_bytes[b_start + 2]

                # If the DIF block headers are not ordered correctly, this DV file is very
                # malformed and beyond the scope of this tool to fix.
                #
                # In practice, my camcorder transmits these even when the tape is blank, so
                # I assume they are always present/accurate.
                assert section_type == dif.DIF_SEQUENCE_TRANSMISSION_ORDER[block]
                assert dif_sequence_number == sequence
                assert fsc == channel
                assert dif_block_number == dif.DIF_BLOCK_NUMBER[block]

                # Track the arbitrary bits
                # Note that the bits for the header and subcode blocks are always
                # 0xF, and other values will make DVRescue malfunction.  There
                # must be some poorly-documented reason for this.
                if (
                    section_type != dif.DIFBlockType.HEADER
                    and section_type != dif.DIFBlockType.SUBCODE
                ):
                    arbitrary_bits_hist[arbitrary_bits] += 1

                if section_type == dif.DIFBlockType.HEADER:
                    # Read header DIF block
                    # SMPTE 306M-2002 Section 11.2.2.1 Header section
                    # APT: SMPTE 306M-2002 Section 6.2.4 Track information area (TIA)
                    # AP1: SMPTE 306M-2002 Section 6.3.3.2 (Audio sync block) ID
                    # AP2: SMPTE 306M-2002 Section 6.4.3.2 (Video sync block) ID
                    # AP3: SMPTE 306M-2002 Section 6.5.3.2 (Subcode sync block) ID
                    dsf = (frame_bytes[b_start + 3] & 0x80) >> 7
                    apt = frame_bytes[b_start + 4] & 0x07
                    tf1 = (frame_bytes[b_start + 5] & 0x80) >> 1
                    ap1 = frame_bytes[b_start + 5] & 0x07
                    tf2 = (frame_bytes[b_start + 6] & 0x80) >> 1
                    ap2 = frame_bytes[b_start + 6] & 0x07
                    tf3 = (frame_bytes[b_start + 7] & 0x80) >> 1
                    ap3 = frame_bytes[b_start + 7] & 0x07

                    # If the DIF sequence flag is wrong, this DV file is very malformed and
                    # beyond the scope of this tool to fix.
                    assert (dsf == 0 and file_info.video_frame_dif_sequence_count == 10) or (
                        dsf == 1 and file_info.video_frame_dif_sequence_count == 12
                    )
                    # Check transmitting flags are all marked as valid
                    assert tf1 == 0  # audio
                    assert tf2 == 0  # VAUX + video
                    assert tf3 == 0  # subcode
                    # Track the application IDs
                    header_track_application_id_hist[apt] += 1
                    header_audio_application_id_hist[ap1] += 1
                    header_video_application_id_hist[ap2] += 1
                    header_subcode_application_id_hist[ap3] += 1
                elif section_type == dif.DIFBlockType.SUBCODE:
                    # Save the subcode blocks for later
                    # SMPTE 306M-2002 Section 11.2.2.2 Subcode section
                    ssyb_len = 8
                    for ssyb_index in range(6):
                        ssyb_start = b_start + 3 + ssyb_len * ssyb_index
                        ssyb_bytes.append(frame_bytes[ssyb_start : ssyb_start + ssyb_len])

                b_start += dif.DIF_BLOCK_SIZE

            # It's quite possible for every last subcode byte to drop out, so track
            # these application IDs separately from the ones in the header block, which
            # are more reliably present.
            # SMPTE 306M-2002 Section 6.5.3.2 (Subcode sync block) ID
            subcode_ap3_from_sync_0 = (ssyb_bytes[0][0] & 0x70) >> 4
            subcode_ap3_from_sync_6 = (ssyb_bytes[6][0] & 0x70) >> 4
            subcode_apt = (ssyb_bytes[11][0] & 0x70) >> 4

            subcode_track_application_id_hist[subcode_apt] += 1
            subcode_subcode_application_id_hist[subcode_ap3_from_sync_0] += 1
            subcode_subcode_application_id_hist[subcode_ap3_from_sync_6] += 1

            # There are 12 subcode sync blocks / subcode packs
            # We record exactly all SSYB pack types in every last channel, sequence, and
            # SSYB pack number.  SMPTE 306M Table 48 defines an SSYB pack layout that
            # looks very different from what my camcorder recorded, so I guess every DV
            # file could be unique.  We'll simply record all information, and leave it to
            # the user to make their own adjustments.
            #
            # However, we will also assume that the data for every pack type will always
            # be exactly the same across every subcode pack in the entire frame.  We'll
            # look for the most common values.
            for ssyb_num in range(12):
                subcode_pack_type = ssyb_bytes[ssyb_num][3]
                subcode_pack_types[channel][sequence][ssyb_num] = subcode_pack_type
                if subcode_pack_type == pack.PackType.TITLE_TIME_CODE:
                    subcode_title_timecode = cast(
                        pack.TitleTimecode,
                        pack.TitleTimecode.parse_binary(
                            ssyb_bytes[ssyb_num][3:],
                            file_info.system,
                        ),
                    )
                    if subcode_title_timecode is not None:
                        subcode_title_timecode_hist[subcode_title_timecode] += 1
                elif subcode_pack_type == pack.PackType.TITLE_BINARY_GROUP:
                    subcode_title_binary_group = cast(
                        pack.TitleBinaryGroup,
                        pack.TitleBinaryGroup.parse_binary(
                            ssyb_bytes[ssyb_num][3:], file_info.system
                        ),
                    )
                    if subcode_title_binary_group is not None:
                        subcode_title_binary_group_hist[subcode_title_binary_group] += 1
                elif subcode_pack_type == pack.PackType.VAUX_RECORDING_DATE:
                    subcode_vaux_recording_date = cast(
                        pack.VAUXRecordingDate,
                        pack.VAUXRecordingDate.parse_binary(
                            ssyb_bytes[ssyb_num][3:], file_info.system
                        ),
                    )
                    if subcode_vaux_recording_date is not None:
                        subcode_vaux_recording_date_hist[subcode_vaux_recording_date] += 1
                elif subcode_pack_type == pack.PackType.VAUX_RECORDING_TIME:
                    subcode_vaux_recording_time = cast(
                        pack.VAUXRecordingTime,
                        pack.VAUXRecordingTime.parse_binary(
                            ssyb_bytes[ssyb_num][3:],
                            file_info.system,
                        ),
                    )
                    if subcode_vaux_recording_time is not None:
                        subcode_vaux_recording_time_hist[subcode_vaux_recording_time] += 1

    return dif.FrameData(
        # DIF block header
        arbitrary_bits=max(arbitrary_bits_hist, key=arbitrary_bits_hist.__getitem__),
        # Header DIF block
        header_track_application_id=max(
            header_track_application_id_hist, key=header_track_application_id_hist.__getitem__
        ),
        header_audio_application_id=max(
            header_audio_application_id_hist, key=header_audio_application_id_hist.__getitem__
        ),
        header_video_application_id=max(
            header_video_application_id_hist, key=header_video_application_id_hist.__getitem__
        ),
        header_subcode_application_id=max(
            header_subcode_application_id_hist,
            key=header_subcode_application_id_hist.__getitem__,
        ),
        # Subcode DIF block
        subcode_track_application_id=max(
            subcode_track_application_id_hist, key=subcode_track_application_id_hist.__getitem__
        ),
        subcode_subcode_application_id=max(
            subcode_subcode_application_id_hist,
            key=subcode_subcode_application_id_hist.__getitem__,
        ),
        subcode_pack_types=subcode_pack_types,
        subcode_title_timecode=(
            max(subcode_title_timecode_hist, key=subcode_title_timecode_hist.__getitem__)
            if subcode_title_timecode_hist
            else pack.TitleTimecode()
        ),
        subcode_title_binary_group=(
            max(subcode_title_binary_group_hist, key=subcode_title_binary_group_hist.__getitem__)
            if subcode_title_binary_group_hist
            else pack.TitleBinaryGroup()
        ),
        subcode_vaux_recording_date=(
            max(subcode_vaux_recording_date_hist, key=subcode_vaux_recording_date_hist.__getitem__)
            if subcode_vaux_recording_date_hist
            else pack.VAUXRecordingDate()
        ),
        subcode_vaux_recording_time=(
            max(subcode_vaux_recording_time_hist, key=subcode_vaux_recording_time_hist.__getitem__)
            if subcode_vaux_recording_time_hist
            else pack.VAUXRecordingTime()
        ),
    )


def read_all_frame_data(input_file: BinaryIO, input_file_info: DVFileInfo) -> list[dif.FrameData]:
    all_frame_data = []
    for frame_number in range(input_file_info.video_frame_count):
        if frame_number % 100 == 0:
            print(f"Reading frame {frame_number} of {input_file_info.video_frame_count}...")

        # Read the bytes for this frame into memory
        input_file.seek(frame_number * input_file_info.video_frame_size)
        frame_bytes = io_util.read_file_bytes(input_file, input_file_info.video_frame_size)
        assert len(frame_bytes) == input_file_info.video_frame_size

        # Parse the frame data
        frame_data = read_frame_data(frame_bytes, input_file_info)
        all_frame_data.append(frame_data)
    return all_frame_data


def write_frame_data(
    frame_bytes: bytearray, file_info: DVFileInfo, frame_data: dif.FrameData
) -> bytearray:
    """Write frame_data into frame_bytes and return updated frame."""

    # Test reading the frame data first, to make sure no assertions fail and
    # that things aren't horribly wrong.  This especially allows us to safely
    # make assumptions about the correct ordering of the DIF block types.
    read_frame_data(frame_bytes, file_info)

    # In general, our approach is to leave unknown/reserved bits
    # as they are, and only change the things we really want to.

    b_start = 0  # current block starting position
    for channel in range(file_info.video_frame_channel_count):
        for sequence in range(file_info.video_frame_dif_sequence_count):
            ssyb_bytes = []  # subcode pack bytes seen in sequence
            ssyb_locations = []  # byte offset for their locations
            ssyb_len = 8
            for block in range(len(dif.DIF_SEQUENCE_TRANSMISSION_ORDER)):
                # read_frame_data already checked for correct transmission order,
                # so we don't need to read the section type from the file.
                section_type = dif.DIF_SEQUENCE_TRANSMISSION_ORDER[block]

                # Write arbitrary bits into the DIF block header for all DIF blocks
                # SMPTE 306M-2002 Section 11.2.1 ID
                #
                # Note that the bits for the header and subcode blocks are always
                # 0xF, and other values will make DVRescue malfunction.  There
                # must be some poorly-documented reason for this.  We'll leave
                # those bits untouched because I don't know what they mean.
                if (
                    section_type != dif.DIFBlockType.HEADER
                    and section_type != dif.DIFBlockType.SUBCODE
                ):
                    frame_bytes[b_start] = (frame_bytes[b_start] & 0xF0) | (
                        frame_data.arbitrary_bits & 0x0F
                    )

                if section_type == dif.DIFBlockType.HEADER:
                    # Write application IDs to the header DIF block
                    # SMPTE 306M-2002 Section 11.2.2.1 Header section
                    # APT: SMPTE 306M-2002 Section 6.2.4 Track information area (TIA)
                    # AP1: SMPTE 306M-2002 Section 6.3.3.2 (Audio sync block) ID
                    # AP2: SMPTE 306M-2002 Section 6.4.3.2 (Video sync block) ID
                    # AP3: SMPTE 306M-2002 Section 6.5.3.2 (Subcode sync block) ID
                    frame_bytes[b_start + 4] = (frame_bytes[b_start + 4] & 0xF8) | (
                        frame_data.header_track_application_id & 0x07
                    )
                    frame_bytes[b_start + 5] = (frame_bytes[b_start + 5] & 0xF8) | (
                        frame_data.header_audio_application_id & 0x07
                    )
                    frame_bytes[b_start + 6] = (frame_bytes[b_start + 6] & 0xF8) | (
                        frame_data.header_video_application_id & 0x07
                    )
                    frame_bytes[b_start + 7] = (frame_bytes[b_start + 7] & 0xF8) | (
                        frame_data.header_subcode_application_id & 0x07
                    )
                elif section_type == dif.DIFBlockType.SUBCODE:
                    # Save the subcode blocks for later
                    # SMPTE 306M-2002 Section 11.2.2.2 Subcode section
                    for ssyb_index in range(6):
                        ssyb_start = b_start + 3 + ssyb_len * ssyb_index
                        ssyb_bytes.append(frame_bytes[ssyb_start : ssyb_start + ssyb_len])
                        ssyb_locations.append(ssyb_start)

                b_start += dif.DIF_BLOCK_SIZE

            # It's quite possible - and common - for every last subcode byte
            # to drop out, so we need to be quite thorough about writing data
            # back out unless otherwise requested.
            assert len(ssyb_bytes) == 12
            for ssyb_num in range(12):
                ssyb_start = ssyb_locations[ssyb_num]
                # Write the ID data.  Note that application IDs are
                # written after the loop.
                # FR bit: set if in first half of the channel
                frame_bytes[ssyb_start] = (frame_bytes[ssyb_start] & 0x7F) | (
                    0x80 if sequence < file_info.video_frame_dif_sequence_count / 2 else 0x00
                )
                # Syb bits: sync block number
                frame_bytes[ssyb_start + 1] = (frame_bytes[ssyb_start + 1] & 0xF0) | ssyb_num
                # IDP parity bit: in practice this is 0xFF on a couple test
                # captures I did.  Also, libdv writes 0xFF for this as well.
                frame_bytes[ssyb_start + 2] = 0xFF

                # Write the subcode pack itself
                pack_start = ssyb_start + 3
                pack_len = 5
                desired_pack_type = frame_data.subcode_pack_types[channel][sequence][ssyb_num]
                if desired_pack_type is None:
                    # User doesn't want to further modify the subcode pack.
                    continue
                elif desired_pack_type == pack.PackType.EMPTY:
                    new_pack = bytes([0xFF] * pack_len)
                elif desired_pack_type == pack.PackType.TITLE_TIME_CODE:
                    assert frame_data.subcode_title_timecode is not None
                    new_pack = frame_data.subcode_title_timecode.to_binary(frame_data.system)
                elif desired_pack_type == pack.PackType.TITLE_BINARY_GROUP:
                    assert frame_data.subcode_title_binary_group is not None
                    new_pack = frame_data.subcode_title_binary_group.to_binary(frame_data.system)
                elif desired_pack_type == pack.PackType.VAUX_RECORDING_DATE:
                    assert frame_data.subcode_vaux_recording_date is not None
                    new_pack = frame_data.subcode_vaux_recording_date.to_binary(frame_data.system)
                elif desired_pack_type == pack.PackType.VAUX_RECORDING_TIME:
                    assert frame_data.subcode_vaux_recording_time is not None
                    new_pack = frame_data.subcode_vaux_recording_time.to_binary(frame_data.system)
                else:
                    raise ValueError(
                        "Unsupported subcode pack type.  Use "
                        "underscores if you don't want to change it."
                    )
                assert len(new_pack) == pack_len
                frame_bytes[pack_start : pack_start + pack_len] = new_pack

            # Always write out the application IDs
            # SMPTE 306M-2002 Section 6.5.3.2 (Subcode sync block) ID
            # Especially see Table 32 - ID data in subcode sector
            frame_bytes[ssyb_locations[0]] = (frame_bytes[ssyb_locations[0]] & 0x8F) | (
                (frame_data.subcode_subcode_application_id & 0x07) << 4
            )
            frame_bytes[ssyb_locations[6]] = (frame_bytes[ssyb_locations[6]] & 0x8F) | (
                (frame_data.subcode_subcode_application_id & 0x07) << 4
            )
            frame_bytes[ssyb_locations[11]] = (frame_bytes[ssyb_locations[11]] & 0x8F) | (
                (frame_data.subcode_track_application_id & 0x07) << 4
            )

    return frame_bytes


def write_all_frame_data(
    input_file: BinaryIO,
    input_file_info: DVFileInfo,
    all_frame_data: list[dif.FrameData],
    output_file: BinaryIO,
) -> None:
    assert input_file_info.video_frame_count == len(all_frame_data)
    for frame_number in range(input_file_info.video_frame_count):
        if frame_number % 100 == 0:
            print(f"Writing frame {frame_number} of {input_file_info.video_frame_count}...")

        # Read the bytes for this frame into memory
        input_file.seek(frame_number * input_file_info.video_frame_size)
        frame_bytes = io_util.read_file_bytes(input_file, input_file_info.video_frame_size)
        assert len(frame_bytes) == input_file_info.video_frame_size

        # Update the frame data in this memory buffer
        frame_bytes = write_frame_data(frame_bytes, input_file_info, all_frame_data[frame_number])

        # Write the bytes for this frame to the output
        output_file.write(frame_bytes)
