import argparse
import csv
import sys
from dataclasses import dataclass
from typing import Iterator, TextIO


class AnalyzeVirtualDubTimingLogArgs(argparse.Namespace):
    timing_log: list[TextIO]
    fps_num: int
    fps_den: int
    fps_tolerance: float
    max_capture_global_difference: float
    max_time_between_audio_frames: float


def parse_args() -> AnalyzeVirtualDubTimingLogArgs:
    parser = argparse.ArgumentParser(
        prog="analyze_virtualdub_timing_log",
        description="Analyze a VirtualDub capture timing log.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "timing_log",
        type=argparse.FileType("rt"),
        nargs=1,
        help="The VirtualDub timing capture log to analyze.",
    )
    parser.add_argument(
        "--fps-num",
        type=int,
        required=True,
        help="Numerator of the capture frame rate (e.g. 30000 for NTSC 29.970).",
    )
    parser.add_argument(
        "--fps-den",
        type=int,
        required=True,
        help="Denominator of the capture frame rate (e.g. 1001 for NTSC 29.970).",
    )
    parser.add_argument(
        "--fps-tolerance",
        type=float,
        default=75.0,
        help="Tolerance of FPS variation in the timings that is considered "
        "acceptable.  The value is a percentage.",
    )
    parser.add_argument(
        "--max-capture-global-difference",
        type=float,
        default=50.0,
        help="Maximum number of milliseconds between video frame capture time and "
        "global time for a single frame.",
    )
    parser.add_argument(
        "--max-time-between-audio-frames",
        type=float,
        default=15.0,
        help="Maximum number of milliseconds between audio frames.",
    )
    return parser.parse_args(namespace=AnalyzeVirtualDubTimingLogArgs())


# all times are in milliseconds...


@dataclass(frozen=True, kw_only=True)
class VideoFrameLog:
    """Timing analysis row from the CSV file for a video frame."""

    captured_frames: int
    capture_time: float
    global_time: float
    size: int
    key: int


@dataclass(frozen=True, kw_only=True)
class AudioFrameLog:
    """Timing analysis row from the CSV file for an audio frame."""

    captured_frames: int
    captured_bytes: int
    global_time: float
    size: int


def parse_timing_log(log_file: Iterator[str]) -> tuple[list[VideoFrameLog], list[AudioFrameLog]]:
    reader = csv.DictReader(log_file, dialect="excel")
    video_frame_log = []
    audio_frame_log = []
    for row in reader:
        if row["VFrames"] != "":
            video_frame_log.append(
                VideoFrameLog(
                    captured_frames=int(row["VFrames"]),
                    capture_time=float(row["VCapTime"]),
                    global_time=float(row["VGlobalTime"]),
                    size=int(row["VSize"]),
                    key=int(row["VKey"]),
                )
            )
        if row["AFrames"] != "":
            audio_frame_log.append(
                AudioFrameLog(
                    captured_frames=int(row["AFrames"]),
                    captured_bytes=int(row["ABytes"]),
                    global_time=float(row["AGlobalTime"]),
                    size=int(row["ASize"]),
                )
            )
    return (video_frame_log, audio_frame_log)


@dataclass(frozen=True, kw_only=True)
class VideoFrameAnalysis:
    """Analysis results for a video frame."""

    log_entry: VideoFrameLog

    capture_time_gap: float | None
    capture_time_gap_abnormal: bool

    global_time_gap: float | None
    global_time_gap_abnormal: bool

    capture_global_difference: float
    capture_global_difference_abnormal: bool


def analyze_video_log(
    video_frame_log: list[VideoFrameLog],
    expected_fps: float,
    fps_tolerance: float,
    max_capture_global_difference: float,
) -> list[VideoFrameAnalysis]:
    expected_frame_time = 1.0 / expected_fps * 1000.0
    max_frame_time = (1.0 + fps_tolerance / 100.0) * expected_frame_time
    min_frame_time = (1.0 - fps_tolerance / 100.0) * expected_frame_time

    last_capture_time: float | None = None
    last_global_time: float | None = None
    log_analysis = []
    for frame in video_frame_log:
        # Check for discontinuities in the individual timestamp columns
        capture_time_gap = None
        global_time_gap = None
        if last_capture_time is not None and last_global_time is not None:
            capture_time_gap = frame.capture_time - last_capture_time
            global_time_gap = frame.global_time - last_global_time

        # Also check for a large difference in timestamps for the current frame
        capture_global_difference = frame.global_time - frame.capture_time

        log_analysis.append(
            VideoFrameAnalysis(
                log_entry=frame,
                capture_time_gap=capture_time_gap,
                capture_time_gap_abnormal=(
                    capture_time_gap is not None
                    and (capture_time_gap > max_frame_time or capture_time_gap < min_frame_time)
                ),
                global_time_gap=global_time_gap,
                global_time_gap_abnormal=(
                    global_time_gap is not None
                    and (global_time_gap > max_frame_time or global_time_gap < min_frame_time)
                ),
                capture_global_difference=capture_global_difference,
                capture_global_difference_abnormal=(
                    abs(capture_global_difference) > max_capture_global_difference
                ),
            )
        )

        last_capture_time = frame.capture_time
        last_global_time = frame.global_time
    return log_analysis


@dataclass(frozen=True, kw_only=True)
class AudioFrameAnalysis:
    """Analysis results for an audio frame."""

    log_entry: AudioFrameLog

    global_time_gap: float | None
    global_time_gap_abnormal: bool


def analyze_audio_log(
    audio_frame_log: list[AudioFrameLog], max_time_between_audio_frames: float
) -> list[AudioFrameAnalysis]:
    last_global_time: float | None = None
    log_analysis = []
    for frame in audio_frame_log:
        # Check for discontinuities in the global timestamps
        global_time_gap = None
        if last_global_time is not None:
            global_time_gap = frame.global_time - last_global_time

        log_analysis.append(
            AudioFrameAnalysis(
                log_entry=frame,
                global_time_gap=global_time_gap,
                global_time_gap_abnormal=(
                    global_time_gap is not None and global_time_gap > max_time_between_audio_frames
                ),
            )
        )

        last_global_time = frame.global_time
    return log_analysis


def print_video_analysis(output_file: TextIO, video_analysis: list[VideoFrameAnalysis]) -> None:
    writer = csv.DictWriter(
        output_file,
        fieldnames=[
            "VFrames",
            "VCapTime",
            "VGlobalTime",
            "VCaptureTimeGap",
            "VCaptureTimeGapAbnormal",
            "VGlobalTimeGap",
            "VGlobalTimeGapAbnormal",
            "VCaptureGlobalTimeDifference",
            "VCaptureGlobalTimeDifferenceAbnormal",
        ],
    )
    writer.writeheader()
    for frame in video_analysis:
        # Only log frames with severe problems.
        if (
            frame.capture_time_gap_abnormal
            or frame.global_time_gap_abnormal
            or frame.capture_global_difference_abnormal
        ):
            writer.writerow(
                {
                    "VFrames": frame.log_entry.captured_frames,
                    "VCapTime": "{:.3f}".format(frame.log_entry.capture_time),
                    "VGlobalTime": "{:.3f}".format(frame.log_entry.global_time),
                    "VCaptureTimeGap": (
                        "{:.3f}".format(frame.capture_time_gap)
                        if frame.capture_time_gap is not None
                        else ""
                    ),
                    "VCaptureTimeGapAbnormal": (
                        "TRUE" if frame.capture_time_gap_abnormal else "FALSE"
                    ),
                    "VGlobalTimeGap": (
                        "{:.3f}".format(frame.global_time_gap)
                        if frame.global_time_gap is not None
                        else ""
                    ),
                    "VGlobalTimeGapAbnormal": (
                        "TRUE" if frame.global_time_gap_abnormal else "FALSE"
                    ),
                    "VCaptureGlobalTimeDifference": "{:.3f}".format(
                        frame.capture_global_difference
                    ),
                    "VCaptureGlobalTimeDifferenceAbnormal": (
                        "TRUE" if frame.capture_global_difference_abnormal else "FALSE"
                    ),
                }
            )


def print_audio_analysis(output_file: TextIO, audio_analysis: list[AudioFrameAnalysis]) -> None:
    writer = csv.DictWriter(
        output_file,
        fieldnames=[
            "AFrames",
            "AGlobalTime",
            "AGlobalTimeGap",
            "AGlobalTimeGapAbnormal",
        ],
    )
    writer.writeheader()
    for frame in audio_analysis:
        # Only log frames with severe problems.
        if frame.global_time_gap_abnormal:
            writer.writerow(
                {
                    "AFrames": frame.log_entry.captured_frames,
                    "AGlobalTime": "{:.3f}".format(frame.log_entry.global_time),
                    "AGlobalTimeGap": (
                        "{:.3f}".format(frame.global_time_gap)
                        if frame.global_time_gap is not None
                        else ""
                    ),
                    "AGlobalTimeGapAbnormal": (
                        "TRUE"  # implied: if frame.global_time_gap_abnormal else "FALSE"
                    ),
                }
            )


def main() -> None:
    args = parse_args()

    video_frame_log, audio_frame_log = parse_timing_log(args.timing_log[0])

    video_analysis = analyze_video_log(
        video_frame_log=video_frame_log,
        expected_fps=float(args.fps_num) / float(args.fps_den),
        fps_tolerance=args.fps_tolerance,
        max_capture_global_difference=args.max_capture_global_difference,
    )
    audio_analysis = analyze_audio_log(
        audio_frame_log=audio_frame_log,
        max_time_between_audio_frames=args.max_time_between_audio_frames,
    )

    print(
        "Analysis results.  Timestamps are milliseconds from "
        "start of video.  Durations are also in milliseconds."
    )
    print()

    print("Video frames with abnormal timings:")
    print()
    print_video_analysis(sys.stdout, video_analysis)
    print()

    print("Audio frames with abnormal timings:")
    print()
    print_audio_analysis(sys.stdout, audio_analysis)
    print()

    print("Carefully check the video at and around these global time positions for:")
    print(" - Null/drop video frames (i.e. inserted/repeated frames).")
    print(" - Incorrect audio/video sync.")
    print(" - Unexpected video frame data.")
    print(" - Audio distortion.")


if __name__ == "__main__":
    main()
