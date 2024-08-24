"""Contains functions for running user-provided commands to repair DV frame data."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import BinaryIO, Iterable

import yaml

import video_tools.dv.dif as dif
import video_tools.dv.dif_csv as dif_csv

MOST_COMMON = "MOST_COMMON"

# Default thresholds
DEFAULT_MAX_CHANGED_PROPORTION = 0.05
DEFAULT_MAX_CONSECUTIVE_MODIFICATIONS = 3


@dataclass
class Thresholds:
    """Thresholds used to avoid accidentally making too many changes."""

    max_changed_proportion: float
    max_consecutive_modifications: int | None


@dataclass
class FrameChangeTracker:
    """Track changed frame statistics in order to watch Thresholds."""

    changed_frames: int = 0
    total_frames: int = 0
    last_consecutive_changed_frames: int = 0


@dataclass
class Command(ABC):
    """Base class for transforming frame data."""

    type: str
    start_frame: int
    end_frame: int | None
    thresholds: Thresholds

    def frame_range(self, all_frame_data: list[dif.FrameData]) -> Iterable[int]:
        """Return iterable of frame numbers that this command is supposed to operate on."""
        return range(
            self.start_frame,
            self.end_frame + 1 if self.end_frame is not None else len(all_frame_data),
        )

    def track_changed_frame(
        self,
        old_frame_data: dif.FrameData,
        new_frame_data: dif.FrameData,
        frame_number: int,
        tracker: FrameChangeTracker,
    ) -> None:
        """Track a changed frame in the FrameChangeTracker."""
        changed = old_frame_data != new_frame_data
        if changed:
            tracker.changed_frames += 1
            tracker.last_consecutive_changed_frames += 1
        else:
            tracker.last_consecutive_changed_frames = 0
        tracker.total_frames += 1

        if (
            self.thresholds.max_consecutive_modifications is not None
            and tracker.last_consecutive_changed_frames
            >= self.thresholds.max_consecutive_modifications
        ):
            raise ValueError(f"ERROR:  Changed too many frames in a row at frame {frame_number}.")

    def track_final_proportion(self, tracker: FrameChangeTracker) -> None:
        """Check the final proportion of changed frames against threshold."""
        proportion = float(tracker.changed_frames) / float(tracker.total_frames)
        print(
            f"Changed {proportion * 100:.2f}%, or {tracker.changed_frames}"
            f" of {tracker.total_frames} frames."
        )
        if proportion > self.thresholds.max_changed_proportion:
            raise ValueError("ERROR:  Changed too high a percentage of frames.")

    @abstractmethod
    def run(self, all_frame_data: list[dif.FrameData]) -> list[dif.FrameData]:
        """Run the command to modify all frames."""
        pass

    def command_expansion(self, all_frame_data: list[dif.FrameData]) -> list[Command]:
        """Split the command into multiple, more granular commands."""
        return [self]


def number_subpattern(field_name: str) -> str:
    return (
        r"((?P<"
        + field_name
        + r"_num>\d+)|(?P<"
        + field_name
        + r"_any>\*)|(\[(?P<"
        + field_name
        + r"_range_start>\d+)\s*,\s*(?P<"
        + field_name
        + r"_range_end>\d+)\]))"
    )


# Matches wildcards for command expansion
subcode_column_full_pattern = re.compile(
    r"^sc_pack_types_"
    + number_subpattern("channel")
    + "_"
    + number_subpattern("dif_sequence")
    + "_"
    + number_subpattern("pack")
    + r"$"
)
# Matches an exact subcode column specification
subcode_column_exact_pattern = re.compile(
    r"^sc_pack_types_(?P<channel>\d+)_(?P<dif_sequence>\d+)_(?P<pack>\d+)$"
)

ConstantValueType = (
    int | dif.ColorFrame | dif.PolarityCorrection | dif.BlankFlag | bytes | str | None
)


@dataclass
class WriteConstantCommand(Command):
    """Writes the same constant value to all specified frames for the given column.

    If the specified value is MOST_COMMON, then the most common value in the given
    frame range will be chosen.

    For subcodes, the column must be specified as potential wildcards in the format
    sc_pack_types_<channel>_<dif sequence>_<pack number>.  That is the same as the
    format from the CSV file but with a pack number suffix so as to allow for
    modifying the packs individually.  Each numeric field can be an actual number,
    an inclusive range in the format "[start, end]", or a complete wildcard "*".
    All matching subcode packs will be modified using the same configured value
    and frame range.
    """

    column: str
    value: ConstantValueType

    def __str__(self) -> str:
        value_str = (
            "most common value"
            if self.value == MOST_COMMON
            else f"value {self.value_str(self.value)}"
        )
        return (
            f"write_constant to {self.column} in frames "
            f"[{self.start_frame}, {self.end_frame}] with {value_str}"
        )

    @staticmethod
    def parse_value_str(column: str, value_str: str | None) -> ConstantValueType:
        """Parse the configured value into the native data type used by FrameData."""
        if value_str == MOST_COMMON:
            return value_str
        value_str = value_str if value_str is not None else ""
        match column:
            case (
                "h_track_application_id"
                | "h_audio_application_id"
                | "h_video_application_id"
                | "h_subcode_application_id"
                | "sc_track_application_id"
                | "sc_subcode_application_id"
            ):
                assert value_str != ""
                return int(value_str, 0)
            case _ if subcode_column_full_pattern.match(column):
                # We used full pattern match because this is called before command expansion
                assert value_str != ""
                return int(value_str, 0)
            case "sc_smpte_timecode_color_frame":
                return dif.ColorFrame[value_str] if value_str != "" else None
            case "sc_smpte_timecode_polarity_correction":
                return dif.PolarityCorrection[value_str] if value_str != "" else None
            case "sc_smpte_timecode_binary_group_flags":
                return int(value_str, 0) if value_str != "" else None
            case "sc_smpte_timecode_blank_flag":
                return dif.BlankFlag[value_str] if value_str != "" else None
            case "sc_rec_date_reserved":
                return int(value_str, 0) if value_str != "" else None
            case "sc_recording_time_reserved":
                b = bytes.fromhex(value_str.removeprefix("0x")) if value_str != "" else None
                assert b is None or len(b) == 4
                return b
            case _:
                raise ValueError(f"Unsupported column {column} for write_constant command.")

    def value_str(self, value: ConstantValueType) -> str | None:
        """Convert the native data type used by FrameData into a configuration string."""
        match self.column:
            case (
                "h_track_application_id"
                | "h_audio_application_id"
                | "h_video_application_id"
                | "h_subcode_application_id"
                | "sc_track_application_id"
                | "sc_subcode_application_id"
            ):
                assert isinstance(value, int)
                return dif_csv.hex_int(value, 1)
            case _ if subcode_column_exact_pattern.match(self.column):
                assert isinstance(value, int)
                return dif_csv.hex_int(value, 2)
            case (
                "sc_smpte_timecode_color_frame"
                | "sc_smpte_timecode_polarity_correction"
                | "sc_smpte_timecode_blank_flag"
            ):
                assert (
                    value is None
                    or isinstance(value, dif.ColorFrame)
                    or isinstance(value, dif.PolarityCorrection)
                    or isinstance(value, dif.BlankFlag)
                )
                return value.name if value is not None else None
            case "sc_smpte_timecode_binary_group_flags":
                assert value is None or isinstance(value, int)
                return dif_csv.hex_int(value, 1) if value is not None else None
            case "sc_rec_date_reserved":
                assert value is None or isinstance(value, int)
                return dif_csv.hex_int(value, 1) if value is not None else None
            case "sc_recording_time_reserved":
                assert value is None or isinstance(value, bytes)
                return dif_csv.hex_bytes(value) if value is not None else None
            case _:
                raise ValueError(f"Unsupported column {self.column} for write_constant command.")

    def get_value_from_frame_data(self, frame_data: dif.FrameData) -> ConstantValueType:
        """Retrieve the value from FrameData using the configured column."""
        match self.column:
            case "h_track_application_id":
                return frame_data.header_track_application_id
            case "h_audio_application_id":
                return frame_data.header_audio_application_id
            case "h_video_application_id":
                return frame_data.header_video_application_id
            case "h_subcode_application_id":
                return frame_data.header_subcode_application_id
            case "sc_track_application_id":
                return frame_data.subcode_track_application_id
            case "sc_subcode_application_id":
                return frame_data.subcode_subcode_application_id
            case _ if (match := subcode_column_exact_pattern.match(self.column)):
                return frame_data.subcode_pack_types[int(match.group("channel"))][
                    int(match.group("dif_sequence"))
                ][int(match.group("pack"))]
            case "sc_smpte_timecode_color_frame":
                return (
                    frame_data.subcode_smpte_timecode.color_frame
                    if frame_data.subcode_smpte_timecode
                    else None
                )
            case "sc_smpte_timecode_polarity_correction":
                return (
                    frame_data.subcode_smpte_timecode.polarity_correction
                    if frame_data.subcode_smpte_timecode
                    else None
                )
            case "sc_smpte_timecode_binary_group_flags":
                return (
                    frame_data.subcode_smpte_timecode.binary_group_flags
                    if frame_data.subcode_smpte_timecode
                    else None
                )
            case "sc_smpte_timecode_blank_flag":
                return (
                    frame_data.subcode_smpte_timecode.blank_flag
                    if frame_data.subcode_smpte_timecode
                    else None
                )
            case "sc_rec_date_reserved":
                return (
                    frame_data.subcode_recording_date.reserved
                    if frame_data.subcode_recording_date
                    else None
                )
            case "sc_recording_time_reserved":
                return (
                    frame_data.subcode_recording_time.reserved
                    if frame_data.subcode_recording_time
                    else None
                )
            case _:
                raise ValueError(f"Unsupported column {self.column} for write_constant command.")

    def set_frame_data_to_parsed_value(
        self, frame_data: dif.FrameData, value: ConstantValueType
    ) -> dif.FrameData:
        """Change the value in FrameData to the given value.

        The value needs to have already been parsed."""
        match self.column:
            case "h_track_application_id":
                assert isinstance(value, int)
                return replace(frame_data, header_track_application_id=value)
            case "h_audio_application_id":
                assert isinstance(value, int)
                return replace(frame_data, header_audio_application_id=value)
            case "h_video_application_id":
                assert isinstance(value, int)
                return replace(frame_data, header_video_application_id=value)
            case "h_subcode_application_id":
                assert isinstance(value, int)
                return replace(frame_data, header_subcode_application_id=value)
            case "sc_track_application_id":
                assert isinstance(value, int)
                return replace(frame_data, subcode_track_application_id=value)
            case "sc_subcode_application_id":
                assert isinstance(value, int)
                return replace(frame_data, subcode_subcode_application_id=value)
            case _ if (match := subcode_column_exact_pattern.match(self.column)):
                # Making a deep copy of frame_data.subcode_pack_types would be
                # the simple and naive way of doing this, but it's very slow.
                # Instead, we'll only copy the lists that we're actually changing.
                assert isinstance(value, int) or value is None
                channel = int(match.group("channel"))
                dif_sequence = int(match.group("dif_sequence"))
                pack = int(match.group("pack"))
                new_channels = frame_data.subcode_pack_types[:]  # shallow copy
                new_dif_sequences = new_channels[channel][:]
                new_packs = new_dif_sequences[dif_sequence][:]
                new_packs[pack] = value
                new_dif_sequences[dif_sequence] = new_packs
                new_channels[channel] = new_dif_sequences
                return replace(frame_data, subcode_pack_types=new_channels)
            case (
                "sc_smpte_timecode_color_frame"
                | "sc_smpte_timecode_polarity_correction"
                | "sc_smpte_timecode_binary_group_flags"
                | "sc_smpte_timecode_blank_flag"
            ):
                existing_timecode = (
                    frame_data.subcode_smpte_timecode
                    if frame_data.subcode_smpte_timecode is not None
                    else dif.SMPTETimecode(
                        hour=None,
                        minute=None,
                        second=None,
                        frame=None,
                        drop_frame=None,
                        color_frame=None,
                        polarity_correction=None,
                        binary_group_flags=None,
                        blank_flag=None,
                        video_frame_dif_sequence_count=len(frame_data.subcode_pack_types[0]),
                    )
                )
                if self.column == "sc_smpte_timecode_color_frame":
                    # physically overlaps with blank_flag on tape
                    assert isinstance(value, dif.ColorFrame) or value is None
                    blank_flag = dif.BlankFlag(value) if value is not None else None
                    new_timecode = replace(
                        existing_timecode, color_frame=value, blank_flag=blank_flag
                    )
                elif self.column == "sc_smpte_timecode_polarity_correction":
                    assert isinstance(value, dif.PolarityCorrection) or value is None
                    new_timecode = replace(existing_timecode, polarity_correction=value)
                elif self.column == "sc_smpte_timecode_binary_group_flags":
                    assert isinstance(value, int) or value is None
                    new_timecode = replace(existing_timecode, binary_group_flags=value)
                elif self.column == "sc_smpte_timecode_blank_flag":
                    # physically overlaps with color_frame on tape
                    assert isinstance(value, dif.BlankFlag) or value is None
                    color_frame = dif.ColorFrame(value) if value is not None else None
                    new_timecode = replace(
                        existing_timecode, color_frame=color_frame, blank_flag=value
                    )
                else:
                    assert False
                new_timecode_optional = new_timecode if not new_timecode.is_empty() else None
                return replace(frame_data, subcode_smpte_timecode=new_timecode_optional)
            case "sc_rec_date_reserved":
                assert isinstance(value, int) or value is None
                existing_recording_date = (
                    frame_data.subcode_recording_date
                    if frame_data.subcode_recording_date is not None
                    else dif.SubcodeRecordingDate(
                        year=None,
                        month=None,
                        day=None,
                        week=None,
                        time_zone_hours=None,
                        time_zone_30_minutes=None,
                        daylight_saving_time=None,
                        reserved=None,
                    )
                )
                new_recording_date = replace(existing_recording_date, reserved=value)
                new_recording_date_optional = (
                    new_recording_date if not new_recording_date.is_empty() else None
                )
                return replace(frame_data, subcode_recording_date=new_recording_date_optional)
            case "sc_recording_time_reserved":
                assert isinstance(value, bytes) or value is None
                existing_recording_time = (
                    frame_data.subcode_recording_time
                    if frame_data.subcode_recording_time is not None
                    else dif.SubcodeRecordingTime(
                        hour=None,
                        minute=None,
                        second=None,
                        frame=None,
                        reserved=None,
                        video_frame_dif_sequence_count=len(frame_data.subcode_pack_types[0]),
                    )
                )
                new_recording_time = replace(existing_recording_time, reserved=value)
                new_recording_time_optional = (
                    new_recording_time if not new_recording_time.is_empty() else None
                )
                return replace(frame_data, subcode_recording_time=new_recording_time_optional)
            case _:
                raise ValueError(f"Unsupported column {self.column} for write_constant command.")

    def run(self, all_frame_data: list[dif.FrameData]) -> list[dif.FrameData]:
        # Look for most frequently occurring values and show them to the user.
        histogram: dict[ConstantValueType, int] = defaultdict(int)
        for frame in self.frame_range(all_frame_data):
            frame_data = all_frame_data[frame]
            histogram[self.get_value_from_frame_data(frame_data)] += 1
        sorted_keys = sorted(histogram, key=lambda k: histogram[k], reverse=True)
        print("Most common values for this field:")
        for key in sorted_keys:
            print(f" - {key!r}: {histogram[key]} frames")

        # Pick the value to write
        chosen_value = sorted_keys[0] if self.value == MOST_COMMON else self.value
        print(f"Using value {self.value_str(chosen_value)}.")

        # Update frames with new value
        tracker = FrameChangeTracker()
        for frame in self.frame_range(all_frame_data):
            frame_data = all_frame_data[frame]
            new_frame_data = self.set_frame_data_to_parsed_value(frame_data, chosen_value)
            all_frame_data[frame] = new_frame_data
            self.track_changed_frame(frame_data, new_frame_data, frame, tracker)
        self.track_final_proportion(tracker)

        return all_frame_data

    def command_expansion(self, all_frame_data: list[dif.FrameData]) -> list[Command]:
        """If the column is subcode, then expand into multiple commands."""
        match = subcode_column_full_pattern.match(self.column)
        if match:
            expanded: list[Command] = []
            channel_count = len(all_frame_data[0].subcode_pack_types)
            dif_sequence_count = len(all_frame_data[0].subcode_pack_types[0])
            pack_count = len(all_frame_data[0].subcode_pack_types[0][0])
            # Loop through all matching subcode indexes
            for channel in range(0, channel_count):
                if match.group("channel_num") is not None and channel != int(
                    match.group("channel_num")
                ):
                    continue
                if match.group("channel_range_start") is not None and (
                    channel < int(match.group("channel_range_start"))
                    or channel > int(match.group("channel_range_end"))
                ):
                    continue
                for dif_sequence in range(0, dif_sequence_count):
                    if match.group("dif_sequence_num") is not None and dif_sequence != int(
                        match.group("dif_sequence_num")
                    ):
                        continue
                    if match.group("dif_sequence_range_start") is not None and (
                        dif_sequence < int(match.group("dif_sequence_range_start"))
                        or dif_sequence > int(match.group("dif_sequence_range_end"))
                    ):
                        continue
                    for pack in range(0, pack_count):
                        if match.group("pack_num") is not None and pack != int(
                            match.group("pack_num")
                        ):
                            continue
                        if match.group("pack_range_start") is not None and (
                            pack < int(match.group("pack_range_start"))
                            or pack > int(match.group("pack_range_end"))
                        ):
                            continue
                        # At this point, we have a matching subcode
                        expanded.append(
                            replace(
                                self,
                                column=f"sc_pack_types_{channel}_{dif_sequence}_{pack}",
                            )
                        )
            return expanded

        return [self]


@dataclass
class RenumberArbitraryBits(Command):
    """Renumbers the arbitrary bits according to the given pattern.

    The initial value will be taken from the first frame if not specified.  The lower
    and upper bounds are inclusive, and define the valid range of arbitrary bit values
    to use.  The step defines how much to increment the arbitrary bits for every frame.
    """

    initial_value: int | None
    lower_bound: int
    upper_bound: int
    step: int

    def __str__(self) -> str:
        return (
            f"renumber_arbitrary_bits in frames [{self.start_frame}, {self.end_frame}] "
            f"with initial_value={self.initial_value}, lower_bound={self.lower_bound}, "
            f"upper_bound={self.upper_bound}, step={self.step}"
        )

    def run(self, all_frame_data: list[dif.FrameData]) -> list[dif.FrameData]:
        # Determine starting value
        next_value = (
            self.initial_value
            if self.initial_value is not None
            else all_frame_data[self.start_frame].arbitrary_bits
        )
        print(f"Using starting value {dif_csv.hex_int(next_value, 1)}...")
        # Quick sanity checks
        assert next_value >= self.lower_bound and next_value <= self.upper_bound
        assert self.step <= self.upper_bound - self.lower_bound + 1
        # Update frames with new value
        tracker = FrameChangeTracker()
        for frame in self.frame_range(all_frame_data):
            # Update arbitrary bits in frame
            frame_data = all_frame_data[frame]
            new_frame_data = replace(frame_data, arbitrary_bits=next_value)
            all_frame_data[frame] = new_frame_data
            self.track_changed_frame(frame_data, new_frame_data, frame, tracker)

            # Calculate next value
            next_value += self.step
            if next_value > self.upper_bound:
                next_value -= self.upper_bound - self.lower_bound + 1

        self.track_final_proportion(tracker)

        return all_frame_data


@dataclass
class RenumberSMPTETimecodes(Command):
    """Renumbers the SMPTE timecodes.

    The initial value will be taken from the first frame if not specified.
    """

    initial_value: str | None

    def __str__(self) -> str:
        return (
            f"renumber_smpte_timecodes in frames "
            f"[{self.start_frame}, {self.end_frame}] "
            f"with initial_value={self.initial_value}"
        )

    def run(self, all_frame_data: list[dif.FrameData]) -> list[dif.FrameData]:
        # Determine starting value
        next_value = (
            dif.SMPTETimecode.parse_all(
                time=self.initial_value,
                color_frame="",
                polarity_correction="",
                binary_group_flags="",
                blank_flag="",
                video_frame_dif_sequence_count=len(all_frame_data[0].subcode_pack_types[0]),
            )
            if self.initial_value is not None
            else all_frame_data[self.start_frame].subcode_smpte_timecode
        )
        assert next_value is not None
        print(f"Using starting value {next_value.format_time_str()}...")
        # Update frames with new value
        tracker = FrameChangeTracker()
        for frame in self.frame_range(all_frame_data):
            # Update timecode in frame, but ONLY the actual time fields
            frame_data = all_frame_data[frame]

            if frame_data.subcode_smpte_timecode is None:
                new_tc = dif.SMPTETimecode(
                    hour=next_value.hour,
                    minute=next_value.minute,
                    second=next_value.second,
                    frame=next_value.frame,
                    drop_frame=next_value.drop_frame,
                    color_frame=None,
                    polarity_correction=None,
                    binary_group_flags=None,
                    blank_flag=None,
                    video_frame_dif_sequence_count=next_value.video_frame_dif_sequence_count,
                )
            else:
                new_tc = replace(
                    frame_data.subcode_smpte_timecode,
                    hour=next_value.hour,
                    minute=next_value.minute,
                    second=next_value.second,
                    frame=next_value.frame,
                    drop_frame=next_value.drop_frame,
                    video_frame_dif_sequence_count=next_value.video_frame_dif_sequence_count,
                )
            new_frame_data = replace(frame_data, subcode_smpte_timecode=new_tc)

            all_frame_data[frame] = new_frame_data
            self.track_changed_frame(frame_data, new_frame_data, frame, tracker)

            # Calculate next value
            next_value = next_value.increment_frame()

        self.track_final_proportion(tracker)

        return all_frame_data


@dataclass
class Transformations:
    commands: list[Command]

    def run(self, frame_data: list[dif.FrameData]) -> list[dif.FrameData]:
        for command in self.commands:
            for expanded_command in command.command_expansion(frame_data):
                print("===================================================")
                print(f"Running command {expanded_command}...")
                frame_data = expanded_command.run(frame_data)
        print("===================================================")
        return frame_data


def load_transformations(transformations_file: BinaryIO) -> Transformations:
    transformations_yaml = yaml.safe_load(transformations_file)

    # Read thresholds
    max_changed_proportion = transformations_yaml.get("thresholds", {}).get(
        "max_changed_proportion", DEFAULT_MAX_CHANGED_PROPORTION
    )
    max_consecutive_modifications = transformations_yaml.get("thresholds", {}).get(
        "max_consecutive_modifications", DEFAULT_MAX_CONSECUTIVE_MODIFICATIONS
    )
    global_thresholds = Thresholds(
        max_changed_proportion=float(max_changed_proportion),
        max_consecutive_modifications=(
            int(max_consecutive_modifications)
            if max_consecutive_modifications is not None
            else None
        ),
    )

    # Read commands
    commands: list[Command] = []
    for command_dict in transformations_yaml.get("commands", []) or []:
        # Look for per-command threshold overrides
        max_changed_proportion = command_dict.get("thresholds", {}).get(
            "max_changed_proportion", global_thresholds.max_changed_proportion
        )
        max_consecutive_modifications = command_dict.get("thresholds", {}).get(
            "max_consecutive_modifications",
            global_thresholds.max_consecutive_modifications,
        )
        local_thresholds = Thresholds(
            max_changed_proportion=float(max_changed_proportion),
            max_consecutive_modifications=(
                int(max_consecutive_modifications)
                if max_consecutive_modifications is not None
                else None
            ),
        )

        # Parse the command itself
        if command_dict["type"] == "write_constant":
            commands.append(
                WriteConstantCommand(
                    type=command_dict["type"],
                    column=command_dict["column"],
                    value=WriteConstantCommand.parse_value_str(
                        command_dict["column"], command_dict.get("value", MOST_COMMON)
                    ),
                    start_frame=command_dict.get("start_frame", 0),
                    end_frame=command_dict.get("end_frame", None),
                    thresholds=local_thresholds,
                )
            )
        elif command_dict["type"] == "renumber_arbitrary_bits":
            commands.append(
                RenumberArbitraryBits(
                    type=command_dict["type"],
                    initial_value=(
                        int(command_dict.get("initial_value", None), 0)
                        if command_dict.get("initial_value", None) is not None
                        else None
                    ),
                    lower_bound=int(command_dict.get("lower_bound", "0x0"), 0),
                    # upper_bound has no reasonable default: every tape deck is different
                    upper_bound=int(command_dict["upper_bound"], 0),
                    step=int(command_dict.get("step", "0x1"), 0),
                    start_frame=command_dict.get("start_frame", 0),
                    end_frame=command_dict.get("end_frame", None),
                    thresholds=local_thresholds,
                )
            )
        elif command_dict["type"] == "renumber_smpte_timecodes":
            commands.append(
                RenumberSMPTETimecodes(
                    type=command_dict["type"],
                    initial_value=command_dict.get("initial_value", None),
                    start_frame=command_dict.get("start_frame", 0),
                    end_frame=command_dict.get("end_frame", None),
                    thresholds=local_thresholds,
                )
            )
        else:
            raise ValueError(f"Unrecognized command {command_dict['type']}.")

    return Transformations(
        commands=commands,
    )
