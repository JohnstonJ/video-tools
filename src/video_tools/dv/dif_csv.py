"""Contains high-level functions for reading and writing frame data in a CSV file."""

import csv
from typing import Iterator, TextIO, cast

import video_tools.dv.data_util as du
import video_tools.dv.dif as dif
import video_tools.dv.dif_pack as pack


def write_frame_data_csv(output_file: TextIO, all_frame_data: list[dif.FrameData]) -> None:
    fieldnames = [
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
        *[
            # Contents of pack types for each channel & DIF sequence is a 24-digit hex
            # string, which is the list of pack types.  Users may replace a digit pair with
            # "__" to leave it unchanged when writing back out to an updated DV file.
            f"sc_pack_types_{channel}_{dif_sequence}"
            for channel in range(len(all_frame_data[0].subcode_pack_types))
            for dif_sequence in range(len(all_frame_data[0].subcode_pack_types[channel]))
        ],
        *du.add_field_prefix("sc_timecode", pack.SMPTETimecode.text_fields).keys(),
        *du.add_field_prefix("sc_timecode_bg", pack.SMPTEBinaryGroup.text_fields).keys(),
        *du.add_field_prefix("sc_rec_date", pack.SubcodeRecordingDate.text_fields).keys(),
        *du.add_field_prefix("sc_rec_time", pack.SubcodeRecordingTime.text_fields).keys(),
    ]
    writer = csv.DictWriter(output_file, fieldnames=fieldnames)
    writer.writeheader()
    for frame_number in range(len(all_frame_data)):
        frame_data = all_frame_data[frame_number]
        row_fields: dict[str, str] = {
            "frame_number": str(frame_number),
            # From all DIF block headers
            "arbitrary_bits": du.hex_int(frame_data.arbitrary_bits, 1),
            # Header DIF block
            "h_track_application_id": du.hex_int(frame_data.header_track_application_id, 1),
            "h_audio_application_id": du.hex_int(frame_data.header_audio_application_id, 1),
            "h_video_application_id": du.hex_int(frame_data.header_video_application_id, 1),
            "h_subcode_application_id": du.hex_int(frame_data.header_subcode_application_id, 1),
            # Subcode DIF block
            "sc_track_application_id": du.hex_int(frame_data.subcode_track_application_id, 1),
            "sc_subcode_application_id": du.hex_int(frame_data.subcode_subcode_application_id, 1),
            # Subcode packs
            **du.add_field_prefix(
                "sc_timecode", frame_data.subcode_smpte_timecode.to_text_values()
            ),
            **du.add_field_prefix(
                "sc_timecode_bg", frame_data.subcode_smpte_binary_group.to_text_values()
            ),
            **du.add_field_prefix(
                "sc_rec_date", frame_data.subcode_recording_date.to_text_values()
            ),
            **du.add_field_prefix(
                "sc_rec_time", frame_data.subcode_recording_time.to_text_values()
            ),
        }
        for channel in range(len(frame_data.subcode_pack_types)):
            for dif_sequence in range(len(frame_data.subcode_pack_types[channel])):
                field_name = f"sc_pack_types_{channel}_{dif_sequence}"
                pack_types = frame_data.subcode_pack_types[channel][dif_sequence]
                row_fields[field_name] = du.hex_bytes(pack_types, allow_optional=True)

        writer.writerow(row_fields)


def read_frame_data_csv(input_file: Iterator[str]) -> list[dif.FrameData]:
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
        assert video_frame_dif_sequence_count == 10 or video_frame_dif_sequence_count == 12

        # Read the subcode pack types
        subcode_pack_types: list[list[list[int | None]]] = [
            [[None for ssyb in range(12)] for sequence in range(video_frame_dif_sequence_count)]
            for channel in range(video_frame_channel_count)
        ]
        for channel in range(video_frame_channel_count):
            for sequence in range(video_frame_dif_sequence_count):
                type_seq = row[f"sc_pack_types_{channel}_{sequence}"].removeprefix("0x")
                type_seq_pairs = [type_seq[i : i + 2] for i in range(0, len(type_seq), 2)]
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
            subcode_smpte_timecode=cast(
                pack.SMPTETimecode,
                pack.SMPTETimecode.parse_text_values(
                    du.select_field_prefix("sc_timecode", row, excluded_prefixes=["sc_timecode_bg"])
                ),
            ),
            subcode_smpte_binary_group=cast(
                pack.SMPTEBinaryGroup,
                pack.SMPTEBinaryGroup.parse_text_values(
                    du.select_field_prefix("sc_timecode_bg", row)
                ),
            ),
            subcode_recording_date=cast(
                pack.SubcodeRecordingDate,
                pack.SubcodeRecordingDate.parse_text_values(
                    du.select_field_prefix("sc_rec_date", row)
                ),
            ),
            subcode_recording_time=cast(
                pack.SubcodeRecordingTime,
                pack.SubcodeRecordingTime.parse_text_values(
                    du.select_field_prefix("sc_rec_time", row)
                ),
            ),
        )
        all_frame_data.append(frame_data)

        current_frame += 1
    return all_frame_data
