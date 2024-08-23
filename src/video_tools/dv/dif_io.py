"""Contains high-level functions for reading and modifying DIF blocks in a DV file."""

from collections import defaultdict

import video_tools.dv.dif as dif
import video_tools.io_util as io_util


def read_frame_data(frame_bytes, file_info):
    b_start = 0  # current block starting position

    # DIF block header
    arbitrary_bits_hist = defaultdict(int)

    # Header DIF block info
    header_track_application_id_hist = defaultdict(int)
    header_audio_application_id_hist = defaultdict(int)
    header_video_application_id_hist = defaultdict(int)
    header_subcode_application_id_hist = defaultdict(int)

    # Subcode DIF block info
    subcode_track_application_id_hist = defaultdict(int)
    subcode_subcode_application_id_hist = defaultdict(int)
    subcode_pack_types = [
        [
            [None for ssyb in range(12)]
            for sequence in range(file_info.video_frame_dif_sequence_count)
        ]
        for channel in range(file_info.video_frame_channel_count)
    ]
    subcode_smpte_timecode_hist = defaultdict(int)
    subcode_smpte_binary_group_hist = defaultdict(int)
    subcode_recording_date_hist = defaultdict(int)
    subcode_recording_time_hist = defaultdict(int)

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
                    assert (
                        dsf == 0 and file_info.video_frame_dif_sequence_count == 10
                    ) or (dsf == 1 and file_info.video_frame_dif_sequence_count == 12)
                    # Check transmitting flags are all marked as valid
                    assert tf1 == 0  # audio
                    assert tf2 == 0  # VAUX + video
                    assert tf3 == 0  # subcode
                    # Track the application IDs
                    header_track_application_id_hist[apt] += 1
                    header_audio_application_id_hist[ap1] += 1
                    header_video_application_id_hist[ap2] += 1
                    header_subcode_application_id_hist[ap3] += 1
                    pass
                elif section_type == dif.DIFBlockType.SUBCODE:
                    # Save the subcode blocks for later
                    # SMPTE 306M-2002 Section 11.2.2.2 Subcode section
                    ssyb_len = 8
                    for ssyb_index in range(6):
                        ssyb_start = b_start + 3 + ssyb_len * ssyb_index
                        ssyb_bytes.append(
                            frame_bytes[ssyb_start : ssyb_start + ssyb_len]
                        )
                    pass

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
                if subcode_pack_type == dif.SSYBPackType.SMPTE_TC:
                    subcode_smpte_timecode = dif.SMPTETimecode.parse_ssyb_pack(
                        ssyb_bytes[ssyb_num][3:],
                        file_info.video_frame_dif_sequence_count,
                    )
                    if subcode_smpte_timecode is not None:
                        subcode_smpte_timecode_hist[subcode_smpte_timecode] += 1
                elif subcode_pack_type == dif.SSYBPackType.SMPTE_BG:
                    subcode_smpte_binary_group = dif.SMPTEBinaryGroup.parse_ssyb_pack(
                        ssyb_bytes[ssyb_num][3:]
                    )
                    if subcode_smpte_binary_group is not None:
                        subcode_smpte_binary_group_hist[subcode_smpte_binary_group] += 1
                elif subcode_pack_type == dif.SSYBPackType.RECORDING_DATE:
                    subcode_recording_date = dif.SubcodeRecordingDate.parse_ssyb_pack(
                        ssyb_bytes[ssyb_num][3:]
                    )
                    if subcode_recording_date is not None:
                        subcode_recording_date_hist[subcode_recording_date] += 1
                elif subcode_pack_type == dif.SSYBPackType.RECORDING_TIME:
                    subcode_recording_time = dif.SubcodeRecordingTime.parse_ssyb_pack(
                        ssyb_bytes[ssyb_num][3:],
                        file_info.video_frame_dif_sequence_count,
                    )
                    if subcode_recording_time is not None:
                        subcode_recording_time_hist[subcode_recording_time] += 1

    return dif.FrameData(
        # DIF block header
        arbitrary_bits=max(arbitrary_bits_hist, key=arbitrary_bits_hist.get),
        # Header DIF block
        header_track_application_id=max(
            header_track_application_id_hist, key=header_track_application_id_hist.get
        ),
        header_audio_application_id=max(
            header_audio_application_id_hist, key=header_audio_application_id_hist.get
        ),
        header_video_application_id=max(
            header_video_application_id_hist, key=header_video_application_id_hist.get
        ),
        header_subcode_application_id=max(
            header_subcode_application_id_hist,
            key=header_subcode_application_id_hist.get,
        ),
        # Subcode DIF block
        subcode_track_application_id=max(
            subcode_track_application_id_hist, key=subcode_track_application_id_hist.get
        ),
        subcode_subcode_application_id=max(
            subcode_subcode_application_id_hist,
            key=subcode_subcode_application_id_hist.get,
        ),
        subcode_pack_types=subcode_pack_types,
        subcode_smpte_timecode=(
            max(subcode_smpte_timecode_hist, key=subcode_smpte_timecode_hist.get)
            if subcode_smpte_timecode_hist
            else None
        ),
        subcode_smpte_binary_group=(
            max(
                subcode_smpte_binary_group_hist, key=subcode_smpte_binary_group_hist.get
            )
            if subcode_smpte_binary_group_hist
            else None
        ),
        subcode_recording_date=(
            max(subcode_recording_date_hist, key=subcode_recording_date_hist.get)
            if subcode_recording_date_hist
            else None
        ),
        subcode_recording_time=(
            max(subcode_recording_time_hist, key=subcode_recording_time_hist.get)
            if subcode_recording_time_hist
            else None
        ),
    )


def read_all_frame_data(input_file, input_file_info):
    all_frame_data = []
    for frame_number in range(input_file_info.video_frame_count):
        if frame_number % 100 == 0:
            print(
                f"Reading frame {frame_number} of {input_file_info.video_frame_count}..."
            )

        # Read the bytes for this frame into memory
        input_file.seek(frame_number * input_file_info.video_frame_size)
        frame_bytes = io_util.read_file_bytes(
            input_file, input_file_info.video_frame_size
        )
        assert len(frame_bytes) == input_file_info.video_frame_size

        # Parse the frame data
        frame_data = read_frame_data(frame_bytes, input_file_info)
        all_frame_data.append(frame_data)
    return all_frame_data
