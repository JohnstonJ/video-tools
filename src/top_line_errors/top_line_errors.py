import numpy

# Temporary workaround due to https://github.com/scikit-video/scikit-video/issues/154
# Must run this code before importing any skvideo packages.
numpy.float = numpy.float64
numpy.int = numpy.int_

import argparse

import skvideo.io


def parse_args():
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
        "--top-n",
        type=int,
        default=1,
        help="Number of horizontal lines with the highest average pixel value to use.",
    )
    parser.add_argument(
        "--output-format",
        choices=["csv", "ConditionalReader"],
        default="ConditionalReader",
        help="Format of the program output.",
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
        default=137.0,
        help="Only output frames where the horizontal line error for the top erroneous lines "
        "exceeds this value.  This threshold identifies bad frames.",
    )
    return parser.parse_args()


def gather_frame_data(filename, num_frames, top_n, debug_frame):
    """Read input video file and calculate per-frame stats."""
    frames = skvideo.io.vreader(filename, num_frames=num_frames)
    frame_number = 0
    frame_data = []
    for frame in frames:
        is_debug = debug_frame == frame_number

        # Frame format is (rows, columns, pixel channels)
        # Start by computing the average for each row.  Assuming the input frame pixels represent
        # error, then this will represent the average error across the row.
        averaged = frame.mean(axis=(1, 2))
        if is_debug:
            print("Mean pixel value for each row, in order of appearance:")
            print(averaged)
            print()

        # Sort in reverse order
        averaged[::-1].sort()
        if is_debug:
            print("Mean pixel value for each row, sorted by value:")
            print(averaged)
            print()

        # Take the top numbers and average them
        averaged.resize((top_n,))
        frame_mean = averaged.mean()

        # Store in output tuple
        frame_data.append((frame_number, frame_mean))

        frame_number += 1

    return frame_data


def filter_frames(frame_data, frame_threshold):
    """Keep only frames where the overall frame error exceeded the threshold."""
    return [frame for frame in frame_data if frame[1] >= frame_threshold]


def sort_frames(frame_data):
    """Sort frames in descending order by frame error."""
    return sorted(frame_data, key=lambda frame: frame[1], reverse=True)


def output_csv(frame_data):
    """Output frame data in CSV format."""
    print("frame_number,error")
    for frame in frame_data:
        print(f"{frame[0]},{frame[1]}")


def output_conditional_reader(frame_data):
    """Output frame data for use with Avisynth ConditionalReader filter."""
    print("# Bad frame numbers for use with Avisynth ConditionalReader")
    print("TYPE bool")
    print("DEFAULT false")
    print()
    for frame in frame_data:
        print(f"# frame {frame[0]} error: {frame[1]}")
        print(f"{frame[0]} true")
        print()


def main():
    args = parse_args()

    frame_data = gather_frame_data(
        filename=args.filename[0],
        num_frames=args.num_frames,
        top_n=args.top_n,
        debug_frame=args.debug_frame,
    )
    frame_data = filter_frames(frame_data, args.frame_threshold)
    frame_data = sort_frames(frame_data)
    if args.debug_frame is None:
        if args.output_format == "csv":
            output_csv(frame_data)
        elif args.output_format == "ConditionalReader":
            output_conditional_reader(frame_data)


if __name__ == "__main__":
    main()
