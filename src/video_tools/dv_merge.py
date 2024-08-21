import argparse
import contextlib
import io
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import video_tools.io_util as io_util


def parse_args():
    parser = argparse.ArgumentParser(
        prog="dv_merge",
        description="N-way merge of equal-length raw DV files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input_files",
        type=str,
        nargs="+",
        help="Input raw DV binary files.  All must be of equal length.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Name of output file.",
    )
    parser.add_argument(
        "--merge-algorithm",
        choices=["analysis", "binary"],
        default="analysis",
        help="How to merge the files.  analysis will pick frames that are reported to "
        "not have errors by DV Analyzer and DVRescue.  binary will do a very simple "
        "byte-by-byte binary merge (only useful for 3 or more inputs).",
    )
    return parser.parse_args()


@dataclass
class DVAnalyzerFrameAnalysis:
    """Contains frame analysis data from DV Analyzer."""

    frame_type: str
    frame_number: int


@dataclass
class DVAnalyzerFileAnalysis:
    """Contains file analysis data from DV Analyzer."""

    frame_count: int
    frame_analysis: dict[int, DVAnalyzerFrameAnalysis]  # keyed by frame number


def parse_dvanalyzer(analysis_bytes):
    """Parse analysis XML from DV Analyzer.  Only error/special frames are returned."""

    analyzed_files = {}  # return value is keyed by filepath, then by frame number
    # loop over all files parsed by DV Analyzer
    root = ET.fromstring(analysis_bytes)
    file_elements = root.findall("./file")
    for file_element in file_elements:
        # then, build a DVAnalyzerFrameAnalysis for each frame in the file
        filepath = file_element.find("./filepath").text
        frame_objects = {}  # keyed by frame number
        for frame in file_element.findall("./frames/frame"):
            frame_analysis = DVAnalyzerFrameAnalysis(
                frame_type=frame.get("type"),
                frame_number=int(frame.find("./frame").text),
            )
            frame_objects[frame_analysis.frame_number] = frame_analysis

        analyzed_files[filepath] = DVAnalyzerFileAnalysis(
            frame_count=int(file_element.find("./frames_count").text),
            frame_analysis=frame_objects,
        )

    return analyzed_files


def run_dvanalyzer(input_filenames):
    """Analyze files using DV Analyzer CLI.  Assumes that the tool is in the path."""

    print("Analyzing input files using DV Analyze...")
    args = [
        "dvanalyzer",
        "--XML",
        "--Verbosity=9",  # Errors and info (including arbitrary bit)
    ] + input_filenames
    analysis_bytes = subprocess.run(args, capture_output=True, check=True).stdout
    return parse_dvanalyzer(analysis_bytes)


@dataclass
class DVRescueFrameAnalysis:
    """Contains frame analysis data from DV Rescue."""

    frame_number: int
    timecode_repeated: bool
    timecode_nonconsecutive: bool


@dataclass
class DVRescueFileAnalysis:
    """Contains file analysis data from DV Rescue."""

    frame_count: int
    frame_analysis: dict[int, DVRescueFrameAnalysis]  # keyed by frame number


def parse_dvrescue_analyzer(analysis_xml_path):
    """Parse analysis XML from DV Analyzer.

    Only special frames of interest are returned."""

    dvrescue_ns = {"dvrescue": "https://mediaarea.net/dvrescue"}

    # loop over all frames parsed by DVRescue
    root = ET.parse(analysis_xml_path).getroot()
    # then, build a DVRescueFrameAnalysis for each frame in the file
    frame_objects = {}  # keyed by frame number
    for frame in root.findall(
        "./dvrescue:media/dvrescue:frames/dvrescue:frame", dvrescue_ns
    ):
        frame_analysis = DVRescueFrameAnalysis(
            frame_number=int(frame.get("n")),
            timecode_repeated=frame.get("tc_r") is not None,
            timecode_nonconsecutive=frame.get("tc_nc") is not None,
        )
        frame_objects[frame_analysis.frame_number] = frame_analysis

    return DVRescueFileAnalysis(
        frame_count=int(
            root.find("./dvrescue:media/dvrescue:frames", dvrescue_ns).get("count")
        ),
        frame_analysis=frame_objects,
    )


def run_dvrescue_analyzer(input_filenames):
    """Analyze files using DVRescue CLI.  Assumes that the tool is in the path."""

    analyzed_files = {}
    for input_filename in input_filenames:
        print(f"Analyzing {input_filename} using DVRescue...")
        analysis_xml_path = "dv_merge_temp.xml"
        Path(analysis_xml_path).unlink(missing_ok=True)
        args = [
            "dvrescue",
            input_filename,
            "-x",
            analysis_xml_path,
            "-v",
            # verbose mode is slow: it writes too much per-frame status to the console
            "0",
        ]
        subprocess.run(args, check=True)
        analyzed_files[input_filename] = parse_dvrescue_analyzer(analysis_xml_path)
        Path(analysis_xml_path).unlink(missing_ok=True)

    return analyzed_files


def validate_inputs(inputs, dvanalyzer_results, dvrescue_results):
    """Validate input data, returning an error string if it fails.

    The frame byte size is returned if there is no error."""

    # Check that the file sizes are all the same
    sz = None
    for path, file in inputs.items():
        file.seek(0, io.SEEK_END)
        this_sz = file.tell()
        file.seek(0)

        if sz is None:
            sz = this_sz
        elif this_sz != sz:
            return (f"File {path} has a different file size.", None)

    # Exit early if we don't have an analysis
    if dvanalyzer_results is None and dvrescue_results is None:
        return (None, None)

    # Validate analysis
    frame_count = None
    for path in inputs.keys():
        # Check that every file has an analysis
        if path not in dvanalyzer_results:
            return (
                f"File {path} was not analyzed by DV Analyzer for some reason.",
                None,
            )
        if path not in dvrescue_results:
            return (f"File {path} was not analyzed by DVRescue for some reason.", None)

        # Check that every file has at least one frame
        dvanalyzer_analysis = dvanalyzer_results[path]
        if not dvanalyzer_analysis.frame_count:
            return (f"File {path} has no frames according to DV Analyzer.", None)
        dvrescue_analysis = dvrescue_results[path]
        if not dvrescue_analysis.frame_count:
            return (f"File {path} has no frames according to DVRescue.", None)

        # Frame count needs to be in agreement between the two tools.
        if dvanalyzer_analysis.frame_count != dvrescue_analysis.frame_count:
            return (
                f"File {path} detected different frame counts between "
                "DV Analyzer and DVRescue",
                None,
            )

        # And that they all have the same frame counts
        if frame_count is None:
            frame_count = dvanalyzer_analysis.frame_count
        elif frame_count != dvanalyzer_analysis.frame_count:
            return (
                f"File {path} has a different frame count than the other files.",
                None,
            )

    # Check that the file size is evenly divisible by the frame count
    if sz % frame_count:
        return (
            f"The file size {sz} is not evenly divisible by the "
            "frame count {frame_count}.",
            None,
        )

    frame_size = int(sz / frame_count)
    return (None, frame_size)


def merge_inputs(inputs, output, dvanalyzer_results, dvrescue_results, frame_size):
    """Merge input files frame by frame, using the analysis to guide."""
    next_frame_num = 0
    while True:
        # read next frame from each input file
        frame_data = {
            input_name: io_util.read_file_bytes(input_stream, frame_size)
            for input_name, input_stream in inputs.items()
        }
        if not len(next(iter(frame_data.values()))):
            break  # EOF

        # keep track of what frame we are processing
        this_frame_num = next_frame_num
        next_frame_num += 1
        if this_frame_num % 500 == 0:
            print(f"Processing frame {this_frame_num}")

        # look for a frame analysis from DV Analyzer that has no error
        clean_dvanalyzer_inputs = set()
        for input_name in inputs.keys():
            this_analysis = dvanalyzer_results[input_name].frame_analysis
            # If DV Analyzer didn't output the frame at all, then it's fine
            if this_frame_num not in this_analysis:
                clean_dvanalyzer_inputs.add(input_name)
                continue

            # Exclude frames marked as error.
            if this_analysis[this_frame_num].frame_type == "error":
                continue

            clean_dvanalyzer_inputs.add(input_name)

        # next, look for frames that don't have errors in DVRescue.
        # (it has been observed that DVRescue may see timecode
        # coherency issues that DV Analyzer does not, and vice versa).
        clean_dvrescue_inputs = set()
        for input_name in inputs.keys():
            this_analysis = dvrescue_results[input_name].frame_analysis
            # If DVRescue didn't output the frame at all, then it's fine
            if this_frame_num not in this_analysis:
                clean_dvrescue_inputs.add(input_name)
                continue

            # Exclude frames that had repeated time codes.  These most often
            # seem to be wrong.
            if this_analysis[this_frame_num].timecode_repeated:
                continue

            clean_dvrescue_inputs.add(input_name)

        # Look for a frame that is clean in both tools, and write it
        wrote_frame = False
        for input_name in inputs.keys():
            if (
                input_name in clean_dvanalyzer_inputs
                and input_name in clean_dvrescue_inputs
            ):
                output.write(frame_data[input_name])
                wrote_frame = True
                break
        if wrote_frame:
            continue

        # At least one tool is reporting errors...
        # Give preference to a clean DVRescue report, first.
        for input_name in inputs.keys():
            if input_name in clean_dvrescue_inputs:
                print(
                    f"WARNING: Frame {this_frame_num} is clean in DVRescue, but has "
                    "issues in DV Analyzer."
                )
                output.write(frame_data[input_name])
                wrote_frame = True
                break
        if wrote_frame:
            continue

        # Otherwise, fall back to a clean DV Analyzer report.
        for input_name in inputs.keys():
            if input_name in clean_dvanalyzer_inputs:
                print(
                    f"WARNING: Frame {this_frame_num} is clean in DV Analyzer, but "
                    "has issues in DVRescue."
                )
                output.write(frame_data[input_name])
                wrote_frame = True
                break
        if wrote_frame:
            continue

        # All inputs have errors, as reported by both tools.
        print(
            f"WARNING: All copies of frame {this_frame_num} have errors in "
            "both DV Analyzer and DVRescue."
        )
        output.write(next(iter(frame_data.values())))


def merge_binary(inputs, output):
    chunk_size = 1048576
    chunk_num = 0
    while True:
        print(f"Processing chunk {chunk_num}")
        chunk_num += 1

        # read chunk_size bytes from each file
        file_chunks = [read_file_bytes(input, chunk_size) for input in inputs.values()]
        this_chunk_size = len(file_chunks[0])
        if this_chunk_size == 0:
            break

        # generate output chunk by choosing the most common byte
        output_chunk = bytearray(this_chunk_size)

        for pos in range(this_chunk_size):
            # concise but slow:
            # bytes_at_position = [chunk[pos] for chunk in file_chunks]
            # most_common_byte, _ = Counter(bytes_at_position).most_common(1)[0]

            # faster way of finding the most common byte
            chunk_byte_histogram = bytearray(256)
            max_count = 0
            max_count_byte_val = -1
            for chunk in file_chunks:
                this_chunk_byte_val = chunk[pos]
                new_count = chunk_byte_histogram[this_chunk_byte_val] + 1
                chunk_byte_histogram[this_chunk_byte_val] = new_count
                if new_count > max_count:
                    max_count = new_count
                    max_count_byte_val = this_chunk_byte_val
            most_common_byte = max_count_byte_val

            output_chunk[pos] = most_common_byte

        # write output chunk
        output.write(output_chunk)


def main():
    args = parse_args()

    input_filenames = args.input_files
    output_filename = args.output

    # open files
    with contextlib.ExitStack() as stack:
        inputs = {
            input_filename: stack.enter_context(open(input_filename, "rb"))
            for input_filename in input_filenames
        }
        output = stack.enter_context(open(output_filename, "wb"))

        if args.merge_algorithm == "analysis":
            print("Merging frames using analysis results.")
            # analyze the files for errors, which will also count the frames
            dvanalyzer_results = run_dvanalyzer(input_filenames)

            # also run the DVRescue analysis tool, which sometimes gives different results
            dvrescue_results = run_dvrescue_analyzer(input_filenames)

            # verify that the sizes match, among other things
            validation_failure, frame_size = validate_inputs(
                inputs, dvanalyzer_results, dvrescue_results
            )
            if validation_failure is not None:
                print(validation_failure)
                exit(1)
            print(f"Frame size is {frame_size} bytes.")

            # merge them
            merge_inputs(
                inputs, output, dvanalyzer_results, dvrescue_results, frame_size
            )
        elif args.merge_algorithm == "binary":
            print("Using simple binary merge algorithm.")
            # verify that the file sizes match
            validation_failure, _ = validate_inputs(inputs, None, None)
            if validation_failure is not None:
                print(validation_failure)
                exit(1)

            merge_binary(inputs, output)


if __name__ == "__main__":
    main()
