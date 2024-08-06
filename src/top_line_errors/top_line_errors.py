import numpy as np

# Temporary workaround due to https://github.com/scikit-video/scikit-video/issues/154
# Must run this code before importing any skvideo packages.
np.float = np.float64
np.int = np.int_

import argparse
from dataclasses import dataclass
import sys

from scipy.ndimage import convolve1d
import skvideo.io


def FrameRangeParser(value):
    frames = value.split(",")
    if len(frames) > 2:
        raise ValueError(
            "Frame range must be in the form frame_num, or start_num,end_num."
        )
    if len(frames) == 2:
        start = int(frames[0])
        end = int(frames[1])
        if start > end:
            raise ValueError("Start from must be <= end frame.")
        return (start, end)

    frame = int(frames[0])
    return (frame, frame + 1)


def parse_args():
    # NOTE: The default values here assume that we are processing a standard
    # definition video, with (converted) RGB values at (130, 130, 130) signifying
    # no changes.  No smaller values are expected, and larger values signify
    # differences between two frames.

    parser = argparse.ArgumentParser(
        prog="top_line_errors",
        description="Output the average error for the most erroneous horizontal lines in "
        "each video frame.  The input file must be the output from the Avisynth Overlay "
        "difference filter.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "filename",
        nargs=1,
        help="Input video file that was generated using the Avisynth Overlay filter in the "
        "difference mode.",
    )
    parser.add_argument(
        "--num-frames",
        type=int,
        default=0,
        help="Number of frames to read from the input file; default is all frames.  A limited "
        "frame count is faster and useful for debugging, but returns incomplete results.",
    )

    parser.add_argument(
        "--frame-error-function",
        choices=["find-dropouts", "mean"],
        required=True,
        help="How to calculate the frame error metric.  find-dropouts is a "
        "horizontal dropout detector.  mean is a simple average of the image data.",
    )
    parser.add_argument(
        "--debug-frame",
        type=int,
        help="If specified, outputs detailed information about a single frame that can be "
        "useful for setting thresholds.  The parameter is a zero-based frame number.",
    )
    parser.add_argument(
        "--frame-threshold",
        type=float,
        # The default value was specifically tuned for find-dropouts.
        default=137.0,
        help="Only output frames where the error metric exceeds this value.  This "
        "threshold identifies bad frames.",
    )
    parser.add_argument(
        "--exclude-frames",
        type=FrameRangeParser,
        nargs="*",
        help="Exclude the given frame numbers in the format start_num,end_num from "
        "the output.  start_num is inclusive, while end_num is exclusive.  Single "
        "integers can also be given to exclude a single frame.",
    )

    parser.add_argument(
        "--output-csv",
        type=argparse.FileType("w"),
        help="Output results to a CSV file.",
    )
    parser.add_argument(
        "--output-avisynth",
        type=argparse.FileType("w"),
        help="Output results to a file for use with AviSynth's ConditionalReader.",
    )

    # Parameters for find_dropouts
    parser.add_argument(
        "--top-n",
        type=int,
        default=1,
        help="find-dropouts: Number of horizontal lines with the highest "
        "overall average pixel value to use.",
    )
    parser.add_argument(
        "--filter-kernel-size",
        type=int,
        # You really want a fairly wide value here, just to focus on only the
        # strongest - i.e. widest - dropouts.  Shorter widths could be very unrelated.
        default=15,
        help="find-dropouts: Each horizontal line is first averaged with "
        "an averaging filter that has this kernel size.",
    )
    parser.add_argument(
        "--min-dropout-intensity",
        type=int,
        default=190,
        help="find-dropouts: The minimum intensity of pixel that must be found in an "
        "averaged horizontal line to detect a dropout.  If an image does not have any "
        "detected dropouts, then it is completely discarded from the results.",
    )
    parser.add_argument(
        "--min-change-intensity",
        type=int,
        default=150,
        help="find-dropouts: The minimum intensity of pixel that must be found in an "
        "averaged horizontal line to detect some changes that were made, which may or "
        "may not be a dropout.  If an image has too many changes, then it is "
        "completely discarded from the results.",
    )
    parser.add_argument(
        "--max-changed-rows",
        type=int,
        default=20,
        help="find-dropouts: The maximum number of changed rows before the frame "
        "is discarded.",
    )
    return parser.parse_args()


@dataclass
class FrameData:
    """Contains information about an analyzed frame."""

    frame_number: int
    error: float


def mean(debug_frame):
    def compute_frame_data(frame_number, frame):
        is_debug = debug_frame == frame_number

        mean = frame.mean()
        if is_debug:
            print(f"Mean value for frame: {mean}")
        return mean

    return compute_frame_data


def find_dropouts(
    top_n,
    filter_kernel_size,
    min_dropout_intensity,
    min_change_intensity,
    max_changed_rows,
    debug_frame,
):
    if filter_kernel_size % 2 != 1:
        raise ValueError("Filter kernel size must be odd.")
    kernel = np.ones(filter_kernel_size) / filter_kernel_size

    def compute_frame_data(frame_number, frame):
        is_debug = debug_frame == frame_number

        # Frame format is (rows, columns, pixel channels)

        # Average the pixel intensities to get (rows, columns)
        intensities = frame.mean(axis=2)

        # Filter out rows that don't have an adequately bright and long bright cluster of pixels
        convolved = convolve1d(intensities, kernel, axis=1)
        dropout_mask = np.any(convolved >= min_dropout_intensity, axis=1)
        if dropout_mask.sum() == 0:
            return None

        dropout_rows = intensities[dropout_mask]

        # Find rows that just have a lot of changes, even if it's not a sharp dropout
        changes_mask = np.any(convolved >= min_change_intensity, axis=1)
        total_changing_rows = changes_mask.sum()
        if total_changing_rows > max_changed_rows:
            # Too much is changing all over this image.  It might be too destructive
            # to use it if these changes have nothing to do with dropouts.
            return None

        # Start by computing the average for each row.  Assuming the input frame
        # pixels represent error, then this will represent the average error across
        # the row.
        averaged = dropout_rows.mean(axis=1)
        if is_debug:
            print("Mean pixel value for each filtered row, in order of appearance:")
            print(averaged)
            print()

        # Sort in reverse order
        averaged[::-1].sort()
        if is_debug:
            print("Mean pixel value for each filtered row, sorted by value:")
            print(averaged)
            print()

        # Take the top numbers and average them
        averaged.resize((top_n,))
        return averaged.mean()

    return compute_frame_data


def gather_frame_data(filename, num_frames, frame_error_function):
    """Read input video file and calculate per-frame stats."""
    frames = skvideo.io.vreader(filename, num_frames=num_frames)
    frame_number = -1
    frame_data = []
    for frame in frames:
        frame_number += 1

        if frame_number % 100 == 0:
            print(f"Processing frame {frame_number}", file=sys.stderr)

        error = frame_error_function(frame_number, frame)
        if error is not None:
            frame_data.append(
                FrameData(
                    frame_number=frame_number,
                    error=error,
                )
            )

    return frame_data


def filter_frames(frame_data, frame_threshold):
    """Keep only frames where the overall frame error exceeded the threshold."""
    return [frame for frame in frame_data if frame.error >= frame_threshold]


def exclude_frames(frame_data, excluded_frames):
    """Remove specific frame numbers from the results."""
    if excluded_frames is None:
        excluded_frames = []
    return [
        frame
        for frame in frame_data
        if not any(
            frame.frame_number >= bounds[0] and frame.frame_number < bounds[1]
            for bounds in excluded_frames
        )
    ]


def sort_frames(frame_data):
    """Sort frames in descending order by frame error."""
    return sorted(frame_data, key=lambda frame: frame.error, reverse=True)


def output_csv(frame_data, file):
    """Output frame data in CSV format."""
    print("frame_number,error", file=file)
    for frame in frame_data:
        print(f"{frame.frame_number},{frame.error}", file=file)


def output_avisynth(frame_data, file):
    """Output frame data for use with Avisynth ConditionalReader filter."""
    print("# Bad frame numbers for use with Avisynth ConditionalReader", file=file)
    print("TYPE bool", file=file)
    print("DEFAULT false", file=file)
    print(file=file)
    for frame in frame_data:
        print(f"# frame {frame.frame_number} error: {frame.error}", file=file)
        print(f"{frame.frame_number} true", file=file)
        print(file=file)


def main():
    args = parse_args()

    if args.frame_error_function == "find-dropouts":
        frame_error_function = find_dropouts(
            top_n=args.top_n,
            filter_kernel_size=args.filter_kernel_size,
            min_dropout_intensity=args.min_dropout_intensity,
            min_change_intensity=args.min_change_intensity,
            max_changed_rows=args.max_changed_rows,
            debug_frame=args.debug_frame,
        )
    elif args.frame_error_function == "mean":
        frame_error_function = mean(debug_frame=args.debug_frame)

    frame_data = gather_frame_data(
        filename=args.filename[0],
        num_frames=args.num_frames,
        frame_error_function=frame_error_function,
    )
    frame_data = filter_frames(frame_data, args.frame_threshold)
    frame_data = exclude_frames(frame_data, args.exclude_frames)
    frame_data = sort_frames(frame_data)
    if args.output_csv:
        output_csv(frame_data, args.output_csv)
    if args.output_avisynth:
        output_avisynth(frame_data, args.output_avisynth)


if __name__ == "__main__":
    main()
