import argparse

import video_tools.dv.dif_csv as dif_csv
import video_tools.dv.dif_io as dif_io
import video_tools.dv.dif_transform as dif_transform
import video_tools.dv.file_info as file_info


class DVRepairArgs(argparse.Namespace):
    input_dv_file: str | None
    input_csv_file: str | None
    output_dv_file: str | None
    output_csv_file: str | None
    transformations_file: str | None


def parse_args() -> DVRepairArgs:
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
        "input_dv_file",
        type=str,
        help="Input raw DV binary file.  It must not be in any kind of container.",
    )
    read.add_argument(
        "output_csv_file",
        type=str,
        help="Name of output CSV file to hold frame data.",
    )

    # Subcommand: transform
    transform = subparsers.add_parser(
        "transform",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Repair frame data inconsistencies in a CSV file by applying transformations.",
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

    # Subcommand: write
    write = subparsers.add_parser(
        "write",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Write frame data from a CSV file into a DV file.",
        description="Reads all frames from a DV file and updates them with frame "
        "data from a CSV file.  Typically the final step in a repair workflow.",
    )
    write.set_defaults(subcommand_function=write_command)
    write.add_argument(
        "input_dv_file",
        type=str,
        help="Input raw DV binary file.  It must not be in any kind of container.",
    )
    write.add_argument(
        "input_csv_file",
        type=str,
        help="Name of output CSV file holding frame data.",
    )
    write.add_argument(
        "output_dv_file",
        type=str,
        help="Output raw DV binary file that has been updated through the CSV file.",
    )

    return parser.parse_args(namespace=DVRepairArgs())


def read_command(args: DVRepairArgs) -> None:
    input_dv_filename = args.input_dv_file
    assert input_dv_filename is not None
    output_csv_filename = args.output_csv_file
    assert output_csv_filename is not None

    print(f"Reading frame data from {input_dv_filename}...")
    with open(input_dv_filename, mode="rb") as input_dv_file:
        info = file_info.read_dv_file_info(input_dv_file)

        frame_data = dif_io.read_all_frame_data(input_dv_file, info)

    print(f"Writing frame data to {output_csv_filename}...")
    with open(output_csv_filename, "wt", newline="") as output_csv_file:
        dif_csv.write_frame_data_csv(output_csv_file, frame_data)


def transform_command(args: DVRepairArgs) -> None:
    input_csv_filename = args.input_csv_file
    assert input_csv_filename is not None
    transformations_filename = args.transformations_file
    assert transformations_filename is not None
    output_csv_filename = args.output_csv_file
    assert output_csv_filename is not None

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


def write_command(args: DVRepairArgs) -> None:
    input_dv_filename = args.input_dv_file
    assert input_dv_filename is not None
    input_csv_filename = args.input_csv_file
    assert input_csv_filename is not None
    output_dv_filename = args.output_dv_file
    assert output_dv_filename is not None

    print(f"Reading frame data from {input_csv_filename}...")
    with open(input_csv_filename, "rt", newline="") as input_csv_file:
        frame_data = dif_csv.read_frame_data_csv(input_csv_file)

    print(f"Opening input DV file {input_dv_filename}...")
    with open(input_dv_filename, mode="rb") as input_dv_file:
        info = file_info.read_dv_file_info(input_dv_file)
        print(f"Opening output DV file {output_dv_filename}...")
        with open(output_dv_filename, mode="wb") as output_dv_file:
            dif_io.write_all_frame_data(input_dv_file, info, frame_data, output_dv_file)


def main() -> None:
    args = parse_args()
    args.subcommand_function(args)


if __name__ == "__main__":
    main()
