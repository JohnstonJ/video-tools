import argparse

import video_tools.dv.dif_csv as dif_csv
import video_tools.dv.dif_io as dif_io
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


def main():
    args = parse_args()
    args.subcommand_function(args)


if __name__ == "__main__":
    main()
