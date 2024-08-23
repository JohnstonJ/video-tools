"""Contains high-level functions for reading and writing frame data in a CSV file."""

import csv
import itertools

import video_tools.dv.dif as dif


def hex_int(int_value, digits, skip_prefix=False):
    return f"0x{int_value:0{digits}X}" if not skip_prefix else f"{int_value:0{digits}X}"


def hex_bytes(bytes_value, allow_optional=False):
    return f"0x" + "".join(
        [
            (
                hex_int(b, 2, skip_prefix=True)
                if not allow_optional or b is not None
                else "__"
            )
            for b in bytes_value
        ]
    )


def write_frame_data_csv(output_file, all_frame_data):
    fieldnames = list(
        itertools.chain.from_iterable(
            [
                [
                    "frame_number",
                    # From all DIF block headers
                    "arbitrary_bits",
                    # Header DIF block
                    "h_track_application_id",
                    "h_audio_application_id",
                    "h_video_application_id",
                    "h_subcode_application_id",
                    # Subcode DIF block
                    "sc_track_application_id",
                    "sc_subcode_application_id",
                ],
                [
                    # Contents of pack types for each channel & DIF sequence is a 24-digit hex string,
                    # which is the list of pack types.  Users may replace a digit pair with "__" to
                    # leave it unchanged when writing back out to an updated DV file.
                    f"sc_pack_types_{channel}_{dif_sequence}"
                    for channel in range(len(all_frame_data[0].subcode_pack_types))
                    for dif_sequence in range(
                        len(all_frame_data[0].subcode_pack_types[channel])
                    )
                ],
                [
                    # Subcode SMPTE time code
                    "sc_smpte_time_code",
                    "sc_smpte_time_code_color_frame",
                    "sc_smpte_time_code_polarity_correction",
                    "sc_smpte_time_code_binary_group_flags",
                    # Subcode SMPTE binary group
                    "sc_smpte_binary_group",  # 8 hex digits
                    # Subcode recording date/time
                    "sc_recording_date",  # year/month/day
                    "sc_recording_date_reserved",  # 8 hex digits
                    "sc_recording_time",  # hour:minute:second[:frame]
                    "sc_recording_time_reserved",  # 8 hex digits
                ],
            ]
        )
    )
    writer = csv.DictWriter(output_file, fieldnames=fieldnames)
    writer.writeheader()
    for frame_number in range(len(all_frame_data)):
        frame_data = all_frame_data[frame_number]
        row_fields = {
            "frame_number": frame_number,
            # From all DIF block headers
            "arbitrary_bits": hex_int(frame_data.arbitrary_bits, 1),
            # Header DIF block
            "h_track_application_id": hex_int(
                frame_data.header_track_application_id, 1
            ),
            "h_audio_application_id": hex_int(
                frame_data.header_audio_application_id, 1
            ),
            "h_video_application_id": hex_int(
                frame_data.header_video_application_id, 1
            ),
            "h_subcode_application_id": hex_int(
                frame_data.header_subcode_application_id, 1
            ),
            # Subcode DIF block
            "sc_track_application_id": hex_int(
                frame_data.subcode_track_application_id, 1
            ),
            "sc_subcode_application_id": hex_int(
                frame_data.subcode_subcode_application_id, 1
            ),
        }
        for channel in range(len(frame_data.subcode_pack_types)):
            for dif_sequence in range(len(frame_data.subcode_pack_types[channel])):
                field_name = f"sc_pack_types_{channel}_{dif_sequence}"
                pack_types = frame_data.subcode_pack_types[channel][dif_sequence]
                row_fields[field_name] = hex_bytes(pack_types, allow_optional=True)
        if frame_data.subcode_smpte_time_code is not None:
            row_fields |= {
                "sc_smpte_time_code": frame_data.subcode_smpte_time_code.format_time_str(),
                "sc_smpte_time_code_color_frame": (
                    frame_data.subcode_smpte_time_code.color_frame.name
                    if frame_data.subcode_smpte_time_code.color_frame is not None
                    else ""
                ),
                "sc_smpte_time_code_polarity_correction": (
                    frame_data.subcode_smpte_time_code.polarity_correction.name
                    if frame_data.subcode_smpte_time_code.polarity_correction
                    is not None
                    else ""
                ),
                "sc_smpte_time_code_binary_group_flags": (
                    hex_int(frame_data.subcode_smpte_time_code.binary_group_flags, 1)
                    if frame_data.subcode_smpte_time_code.binary_group_flags is not None
                    else ""
                ),
            }
        if frame_data.subcode_smpte_binary_group is not None:
            row_fields |= {
                "sc_smpte_binary_group": hex_bytes(
                    frame_data.subcode_smpte_binary_group.value
                ),
            }
        if frame_data.subcode_recording_date is not None:
            row_fields |= {
                "sc_recording_date": frame_data.subcode_recording_date.format_date_str(),
                "sc_recording_date_reserved": (
                    hex_bytes(frame_data.subcode_recording_date.reserved)
                    if frame_data.subcode_recording_date.reserved is not None
                    else ""
                ),
            }
        if frame_data.subcode_recording_time is not None:
            row_fields |= {
                "sc_recording_time": frame_data.subcode_recording_time.format_time_str(),
                "sc_recording_time_reserved": (
                    hex_bytes(frame_data.subcode_recording_time.reserved)
                    if frame_data.subcode_recording_time.reserved is not None
                    else ""
                ),
            }

        writer.writerow(row_fields)


def read_frame_data_csv(input_file):
    reader = csv.DictReader(input_file)
    all_frame_data = []
    current_frame = 0
    for row in reader:
        assert current_frame == int(row["frame_number"])

        # Derive video dimensions from the subcode type columns
        video_frame_channel_count = 0
        while f"sc_pack_types_{video_frame_channel_count}_0" in row:
            video_frame_channel_count += 1
        video_frame_dif_sequence_count = 0
        while f"sc_pack_types_0_{video_frame_dif_sequence_count}" in row:
            video_frame_dif_sequence_count += 1
        assert video_frame_channel_count < 2
        assert (
            video_frame_dif_sequence_count == 10 or video_frame_dif_sequence_count == 12
        )

        # Read the subcode pack types
        subcode_pack_types = [
            [
                [None for ssyb in range(12)]
                for sequence in range(video_frame_dif_sequence_count)
            ]
            for channel in range(video_frame_channel_count)
        ]
        for channel in range(video_frame_channel_count):
            for sequence in range(video_frame_dif_sequence_count):
                type_seq = row[f"sc_pack_types_{channel}_{sequence}"].removeprefix("0x")
                type_seq_pairs = [
                    type_seq[i : i + 2] for i in range(0, len(type_seq), 2)
                ]
                type_bytes = [
                    (int(type_seq_str, 16) if type_seq_str != "__" else None)
                    for type_seq_str in type_seq_pairs
                ]
                assert len(type_bytes) == 12
                for ssyb in range(12):
                    subcode_pack_types[channel][sequence][ssyb] = type_bytes[ssyb]

        frame_data = dif.FrameData(
            # From DIF block headers
            arbitrary_bits=int(row["arbitrary_bits"], 0),
            # From header DIF block
            header_track_application_id=int(row["h_track_application_id"], 0),
            header_audio_application_id=int(row["h_audio_application_id"], 0),
            header_video_application_id=int(row["h_video_application_id"], 0),
            header_subcode_application_id=int(row["h_subcode_application_id"], 0),
            # From subcode DIF block
            subcode_track_application_id=int(row["sc_track_application_id"], 0),
            subcode_subcode_application_id=int(row["sc_subcode_application_id"], 0),
            subcode_pack_types=subcode_pack_types,
            subcode_smpte_time_code=dif.SMPTETimeCode.parse_all(
                time=row["sc_smpte_time_code"],
                color_frame=row["sc_smpte_time_code_color_frame"],
                polarity_correction=row["sc_smpte_time_code_polarity_correction"],
                binary_group_flags=row["sc_smpte_time_code_binary_group_flags"],
                video_frame_dif_sequence_count=video_frame_dif_sequence_count,
            ),
            subcode_smpte_binary_group=dif.SMPTEBinaryGroup.parse_all(
                value=row["sc_smpte_binary_group"],
            ),
            subcode_recording_date=dif.SubcodeRecordingDate.parse_all(
                date=row["sc_recording_date"],
                reserved=row["sc_recording_date_reserved"],
            ),
            subcode_recording_time=dif.SubcodeRecordingTime.parse_all(
                time=row["sc_recording_time"],
                reserved=row["sc_recording_time_reserved"],
                video_frame_dif_sequence_count=video_frame_dif_sequence_count,
            ),
        )
        all_frame_data.append(frame_data)

        current_frame += 1
    return all_frame_data
