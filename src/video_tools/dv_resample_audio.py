import argparse
import csv
import io
from dataclasses import dataclass

import av
import numpy as np
from av.audio.frame import AudioFrame
from av.filter import Graph

import video_tools.dv.file_info as dv_file_info
import video_tools.io_util as io_util


def parse_args():
    parser = argparse.ArgumentParser(
        prog="dv_resample_audio",
        description="Resample unlocked DV audio to lock it to individual frames "
        "by resampling audio on a frame-by-frame basis.  Smarter than the average "
        "naive approach of resampling the entire audio track at once: this script "
        "will account for a varying clock drift when the audio was recorded, such "
        "as due to changing camera temperatures, etc.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Input raw DV binary file.  It must not be in any kind of container.",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Name of output MKV file to hold audio streams.",
    )
    parser.add_argument(
        "--stats",
        type=str,
        help="Name of output CSV file to write frame-by-frame audio stats/timing to.",
    )
    return parser.parse_args()


@dataclass
class AudioStreamStats:
    """Contains information about a group of audio samples in a single audio stream."""

    actual_sample_count: int  # actual number of audio samples in the video segment
    expected_sample_count: int  # ideal number of audio samples in the video segment

    diff_sample_count: int  # actual - expected sample count
    accumulated_diff_sample_count: int  # diff_sample_count summed up to this point
    accumulated_diff_seconds: int  # accumulated sync error in seconds

    missing_frames: list[int]  # video frame numbers completely missing audio data


@dataclass
class AudioStats:
    """Contains information about a group of audio samples and how they relate to video sync."""

    video_start_frame_number: int  # frame index of first frame in group
    video_frame_count: int  # number of video frames in group
    audio_stream_stats: list[AudioStreamStats]


def resample_audio_frame(audio_frame, video_frame_count, input_file_info):
    """Resample/resync an audio frame that spans several video frames.

    This will return a perfectly exact number of audio samples that matches what would
    ideally be expected given the video frame rate and corresponding video frame count.

    Note that the input audio_frame will be modified with the true sample rate.
    """

    # This is usually going to be an integer, but might be fractional at the end of the
    # entire video when video_frame_count can't hold an integer number of audio samples.
    expected_sample_count = round(video_frame_count * input_file_info.audio_samples_per_frame())

    # This defines the maximum number of frames we will adjust by inserting silence or deleting.
    max_samples_to_finetune = 2  # resampling can be no more than 2 samples off

    # If the expected sample count equals the actual sample count, we don't need to do anything.
    if audio_frame.samples == expected_sample_count:
        return audio_frame

    # If the number of audio samples is off by only a very small amount, we'll just do a resize
    # to truncate or insert silence.  Running the full resample filter would be pointless because
    # we'd be making these same adjustments afterwards anyway due to rounding errors.
    if abs(audio_frame.samples - expected_sample_count) <= max_samples_to_finetune:
        frame_data = audio_frame.to_ndarray()
        frame_data.resize((1, expected_sample_count * 2))
        new_audio_frame = AudioFrame.from_ndarray(frame_data, format="s16", layout="stereo")
        new_audio_frame.sample_rate = input_file_info.audio_sample_rate
        return new_audio_frame

    # Calculate the true sample rate of the audio samples... at least relative to the video
    # clock / frame rate.
    total_video_frame_time = video_frame_count / input_file_info.video_frame_rate
    real_input_sample_rate = audio_frame.samples / total_video_frame_time
    audio_frame.sample_rate = round(real_input_sample_rate)

    # Configure audio resample filter.  This gets us most of the way there, but we'll still be
    # off by maybe a sample due to rounding errors caused by the fact that sample rates are
    # integers.
    graph = Graph()
    abuffer = graph.add(
        "abuffer",
        sample_rate=str(audio_frame.sample_rate),
        sample_fmt=audio_frame.format.name,
        channel_layout=audio_frame.layout.name,
    )
    aresample = graph.add(
        "aresample",
        out_sample_rate=str(input_file_info.audio_sample_rate),
    )
    abuffersink = graph.add("abuffersink")
    abuffer.link_to(aresample)
    aresample.link_to(abuffersink)
    graph.configure()

    # Run the filter
    graph.push(audio_frame)
    graph.push(None)  # EOF

    # Gather filter output into a single large ndarray
    output_frames = []
    while True:
        try:
            output_frames.append(graph.pull().to_ndarray())
        except EOFError:
            break
    resampled_frame_data = np.concatenate(output_frames, axis=1, dtype=np.int16, casting="no")

    # The resample should have gotten us most of the way there, other than a frame or two due to
    # rounding error.  If this assertion fails, something more serious is wrong with the resample.
    assert resampled_frame_data.size > 0
    assert resampled_frame_data.shape[0] == 1
    assert resampled_frame_data.shape[1] % 2 == 0
    assert (
        abs(int(resampled_frame_data.shape[1] / 2) - expected_sample_count)
        <= max_samples_to_finetune
    )

    # Next, fine-tine the sample rate by inserting silence or discarding samples
    resampled_frame_data.resize((1, expected_sample_count * 2))
    new_audio_frame = AudioFrame.from_ndarray(resampled_frame_data, format="s16", layout="stereo")
    new_audio_frame.sample_rate = input_file_info.audio_sample_rate
    return new_audio_frame


def resync_audio(
    input_file,
    input_file_info,
    output,
    start_frame_number,
    max_frames_in_group,
    last_audio_stats,
):
    assert start_frame_number < input_file_info.video_frame_count
    # This is the number of video frames we'll read and resample
    group_size = min(max_frames_in_group, input_file_info.video_frame_count - start_frame_number)
    # This is the total number of audio samples we will resample to; this will be an integer
    # except at the end of the input video:
    ideal_group_audio_samples = round(group_size * input_file_info.audio_samples_per_frame())

    # Read ONLY the next group_size video frames from the input file.  This is extremely critical
    # so that we are effectively ONLY looking at this physical location in the videotape.  It
    # avoids the possibility of audio clock error accumulating.
    input_file.seek(start_frame_number * input_file_info.video_frame_size)
    bytes_to_read = group_size * input_file_info.video_frame_size
    group_bytes = io_util.read_file_bytes(input_file, bytes_to_read)
    assert len(group_bytes) == bytes_to_read
    with io.BytesIO(group_bytes) as group_file:
        # Make sure the audio format or frame rate didn't unexpectedly change on us.  (Could
        # happen if there were multiple recordings from different equipment on the same tape.)
        group_info = dv_file_info.read_dv_file_info(group_file)
        input_file_info.assert_similar(group_info)

        # Read all audio samples from these few video frames.
        group_file.seek(0)
        audio_stats = []
        with av.open(group_file, mode="r", format="dv") as group_container:
            for audio_stream_number in range(len(group_container.streams.audio)):
                # When decoding a DV container, we expect to see a stream of packets and frames:
                #
                #     Packet from video stream for 1 video frame
                #     VideoFrame
                #     Packet from audio stream for audio from 1 video frame
                #     AudioFrame
                #     <repeats>
                #
                # In this case, the audio stream will have a full set of samples for each frame,
                # even if the underlying DV data had a few minor audio errors/dropouts.
                #
                # However, sometimes, a video frame won't have any audio muxed into it at all.
                # What's worse, the Packet and AudioFrame timestamps are also then very
                # inaccurate, and don't account for this gap.
                #
                # To detect these gaps, there seem to be two options:
                #  - Examine the file position of the Packet and look for gaps.
                #  - Demux the video stream as well, and look for back-to-back video
                #    packets/frames that didn't have an audio frame between them.
                # This program takes the first approach of looking at the file position, since
                # demuxing the video stream as well results in an EOF exception if the container
                # has no audio packets what-so-ever for this audio stream.

                # Build a map of relative video frame number in this frame group, to the actual
                # audio frame data:
                audio_frame_map = {}
                audio_stream = group_container.streams.audio[audio_stream_number]
                total_samples = 0
                for packet in group_container.demux(audio_stream):
                    if packet.pos is None:  # placeholder packet at end of stream
                        continue
                    # convert packet position into video frame number
                    assert packet.pos % input_file_info.video_frame_size == 0
                    relative_frame_number = int(packet.pos / input_file_info.video_frame_size)
                    assert relative_frame_number < group_size

                    for frame in packet.decode():
                        assert relative_frame_number not in audio_frame_map
                        audio_frame_map[relative_frame_number] = frame

                # Now, gather the frame data into a list of numpy arrays.  If there are any
                # missing frames, then backfill the frame data with silence.
                missing_frames = []
                all_frame_data = []
                for relative_frame_number in range(group_size):
                    if relative_frame_number not in audio_frame_map:  # missing frame
                        missing_frames.append(start_frame_number + relative_frame_number)
                        # dither the sample count for missing frames, so that we don't accumulate
                        # significant error just from backfilling several consecutive frames:
                        missing_frame_sample_count = round(
                            (relative_frame_number + 1) * (ideal_group_audio_samples / group_size)
                        ) - round(relative_frame_number * (ideal_group_audio_samples / group_size))
                        total_samples += missing_frame_sample_count
                        # fill the space with silence (multiply by 2 because stereo channels)
                        all_frame_data.append(
                            np.zeros((1, missing_frame_sample_count * 2), dtype=np.int16)
                        )
                    else:
                        this_frame = audio_frame_map[relative_frame_number]
                        total_samples += this_frame.samples
                        all_frame_data.append(this_frame.to_ndarray())

                # Append all the frame data together into one gigantic AudioFrame.
                appended_frame_data = np.concatenate(
                    all_frame_data, axis=1, dtype=np.int16, casting="no"
                )
                assert appended_frame_data.shape[0] == 1
                assert appended_frame_data.shape[1] == total_samples * 2
                appended_audio_frame = AudioFrame.from_ndarray(
                    appended_frame_data, format="s16", layout="stereo"
                )
                appended_audio_frame.sample_rate = input_file_info.audio_sample_rate

                # Resample that AudioFrame to the correct number of samples.
                resampled_frame = resample_audio_frame(
                    appended_audio_frame, group_size, input_file_info
                )

                # Write the output frame
                output_packets = output.streams.audio[audio_stream_number].codec_context.encode(
                    resampled_frame
                )
                for output_packet in output_packets:
                    output_packet.stream = output.streams.audio[audio_stream_number]
                    output.mux_one(output_packet)

                # Gather audio stats for this stream
                diff_sample_count = total_samples - ideal_group_audio_samples
                accumulated_diff_sample_count = (
                    last_audio_stats.audio_stream_stats[
                        audio_stream_number
                    ].accumulated_diff_sample_count
                    if last_audio_stats
                    else 0
                ) + diff_sample_count
                accumulated_diff_seconds = (
                    float(accumulated_diff_sample_count) / input_file_info.audio_sample_rate
                )
                audio_stats.append(
                    AudioStreamStats(
                        actual_sample_count=total_samples,
                        expected_sample_count=ideal_group_audio_samples,
                        diff_sample_count=diff_sample_count,
                        accumulated_diff_sample_count=accumulated_diff_sample_count,
                        accumulated_diff_seconds=accumulated_diff_seconds,
                        missing_frames=missing_frames,
                    )
                )

        # Return the audio stats
        return AudioStats(
            video_start_frame_number=start_frame_number,
            video_frame_count=group_size,
            audio_stream_stats=audio_stats,
        )


def resync_all_audio(input_file, input_file_info, output_filename):
    with av.open(output_filename, "w") as output:
        for s in range(input_file_info.audio_stereo_channel_count):
            output.add_stream("pcm_s16le", rate=input_file_info.audio_sample_rate)

        frames_in_group = input_file_info.audio_samples_per_frame().denominator
        all_audio_stats = []
        last_audio_stats = None

        group_number = 0
        for frame_number in range(0, input_file_info.video_frame_count, frames_in_group):
            if group_number % 10 == 0:
                print(f"Processing frames at {frame_number}...")
            group_number += 1

            last_audio_stats = resync_audio(
                input_file,
                input_file_info,
                output,
                frame_number,
                frames_in_group,
                last_audio_stats,
            )
            all_audio_stats.append(last_audio_stats)
        return all_audio_stats


def write_audio_stats(file, file_info, all_stats):
    fieldnames = [
        "video_start_frame_number",
        "video_frame_count",
    ]
    for audio_stream_number in range(file_info.audio_stereo_channel_count):
        fieldnames.append(f"audio_{audio_stream_number}_actual_sample_count")
        fieldnames.append(f"audio_{audio_stream_number}_expected_sample_count")
        fieldnames.append(f"audio_{audio_stream_number}_diff_sample_count")
        fieldnames.append(f"audio_{audio_stream_number}_accumulated_diff_sample_count")
        fieldnames.append(f"audio_{audio_stream_number}_accumulated_diff_seconds")
        fieldnames.append(f"audio_{audio_stream_number}_missing_frames")

    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    for stats in all_stats:
        row_fields = {
            "video_start_frame_number": stats.video_start_frame_number,
            "video_frame_count": stats.video_frame_count,
        }
        for audio_stream_number in range(file_info.audio_stereo_channel_count):
            row_fields[f"audio_{audio_stream_number}_actual_sample_count"] = (
                stats.audio_stream_stats[audio_stream_number].actual_sample_count
            )
            row_fields[f"audio_{audio_stream_number}_expected_sample_count"] = (
                stats.audio_stream_stats[audio_stream_number].expected_sample_count
            )
            row_fields[f"audio_{audio_stream_number}_diff_sample_count"] = stats.audio_stream_stats[
                audio_stream_number
            ].diff_sample_count
            row_fields[f"audio_{audio_stream_number}_accumulated_diff_sample_count"] = (
                stats.audio_stream_stats[audio_stream_number].accumulated_diff_sample_count
            )
            row_fields[f"audio_{audio_stream_number}_accumulated_diff_seconds"] = (
                stats.audio_stream_stats[audio_stream_number].accumulated_diff_seconds
            )
            row_fields[f"audio_{audio_stream_number}_missing_frames"] = str(
                stats.audio_stream_stats[audio_stream_number].missing_frames
            )

        writer.writerow(row_fields)


def main():
    args = parse_args()

    input_filename = args.input_file
    output_filename = args.output
    stats_filename = args.stats

    with open(input_filename, mode="rb") as input_file:
        file_info = dv_file_info.read_dv_file_info(input_file)

        all_audio_stats = resync_all_audio(input_file, file_info, output_filename)

    if stats_filename is not None:
        with open(stats_filename, "wt", newline="") as stats_file:
            write_audio_stats(stats_file, file_info, all_audio_stats)


if __name__ == "__main__":
    main()
