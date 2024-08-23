import argparse

import video_tools.dv.dif_csv as dif_csv
import video_tools.dv.dif_io as dif_io
import video_tools.dv.dif_transform as dif_transform
import video_tools.dv.file_info as file_info


def parse_args():
    parser = argparse.ArgumentParser(
        prog="dv_repair",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Provides tools for viewing and editing DV data.",
    )
    subparsers = parser.add_subparsers(
        description="Use these subcommands to perform various repair "
        "operations in the repair workflow.",
        required=True,
    )

    # Subcommand: read
    read = subparsers.add_parser(
        "read",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Read all frame data from a DV file and write it to a CSV file.",
        description="Read all frame data from a DV file and write it to a CSV file "
        "for subsequent repairs.  Typically the first step in a repair workflow.  "
        "You can later use the transform command to fix detected problems "
        "in the CSV file.",
    )
    read.set_defaults(subcommand_function=read_command)
    read.add_argument(
        "input_file",
        type=str,
        help="Input raw DV binary file.  It must not be in any kind of container.",
    )
    read.add_argument(
        "--output-csv",
        type=str,
        help="Name of output CSV file to hold frame data.  By default, it will "
        "be the name of the input file with a .csv suffix.",
    )

    # Subcommand: transform
    transform = subparsers.add_parser(
        "transform",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Repair frame data inconsistencies in a CSV file by applying "
        "transformations.",
        description="Read frame data from a CSV file previously created by the "
        "read or transform commands.  Then, run a series of transformations in "
        "a user-provided YAML file to repair the frame data in this file.  The "
        "transformed output is written to a new CSV file.  Typically the second "
        "step in a repair workflow.  You can later use the write command to "
        "write the corrected frame data in the CSV file back to a DV file.",
    )
    transform.set_defaults(subcommand_function=transform_command)
    transform.add_argument(
        "input_csv_file",
        type=str,
        help="Input CSV file previously created by the read or transform commands.",
    )
    transform.add_argument(
        "transformations_file",
        type=str,
        help="Input YAML file containing a list of transformations to run.",
    )
    transform.add_argument(
        "output_csv_file",
        type=str,
        help="Output CSV file that will hold the transformed output.",
    )

    return parser.parse_args()


def read_command(args):
    input_filename = args.input_file
    output_csv_filename = args.output_csv
    if output_csv_filename is None:
        output_csv_filename = input_filename + ".csv"

    print(f"Reading frame data from {input_filename}...")
    with open(input_filename, mode="rb") as input_file:
        info = file_info.read_dv_file_info(input_file)

        frame_data = dif_io.read_all_frame_data(input_file, info)

    print(f"Writing frame data to {output_csv_filename}...")
    with open(output_csv_filename, "wt", newline="") as output_csv_file:
        dif_csv.write_frame_data_csv(output_csv_file, frame_data)


def transform_command(args):
    input_csv_filename = args.input_csv_file
    transformations_filename = args.transformations_file
    output_csv_filename = args.output_csv_file

    print(f"Reading frame data from {input_csv_filename}...")
    with open(input_csv_filename, "rt", newline="") as input_csv_file:
        frame_data = dif_csv.read_frame_data_csv(input_csv_file)

    print(f"Transforming frame data using {transformations_filename}...")
    with open(transformations_filename, "rb") as transformations_file:
        transformations = dif_transform.load_transformations(transformations_file)
        frame_data = transformations.run(frame_data)

    print(f"Writing frame data to {output_csv_filename}...")
    with open(output_csv_filename, "wt", newline="") as output_csv_file:
        dif_csv.write_frame_data_csv(output_csv_file, frame_data)


def main():
    args = parse_args()
    args.subcommand_function(args)


if __name__ == "__main__":
    main()
