# dv_resample_audio

DV files can exhibit audio/video desynchronization that can drift randomly throughout the length of the video.  It can sometimes become quite severe.  Most frustratingly, the audio may appear desynchronized only under certain conditions.  The root cause is often that the camera may not have had an audio clock that was locked to the video clock.  This subject of unlocked audio is discussed more by [Adam Wilt](https://www.adamwilt.com/DV-FAQ-tech.html#LockedAudio).  This situation is most common with consumer DV camcorders.

A DV file organizes audio/video data by video frame.  Each video frame also contains a variable number of audio samples that have been muxed into it by the camera.  This sample count might be more or less than what would be ideally expected given the declared audio sample rate in the video metadata.  If it's consistently off, then the audio may drift away from the video if the video is played or processed from the start.

This tool fixes these problems by resampling the audio from a DV file such that every video frame effectively contains the exact number of expected audio frames.  It is basically like reclocking / locking the audio to the video by looking at the physical position of the audio samples in relation to the video frame data on the underlying videotape.

Although this tool will almost certainly be beneficial for DV files recorded by cameras with unlocked audio, it can also be useful for DV files recorded by cameras with locked audio as well.  In the latter case, the output CSV file can be analyzed to verify that the audio was really locked.

## Example workflow

1.  The tool only works with bare DV files that don't have any container (e.g. AVI, MOV, MKV files).  Use FFmpeg to strip off the container if there is one:

    ```
    ffmpeg -i captured.mkv -map 0:v:0 -c copy -f rawvideo captured.dv
    ```

2.  Run the `dv_resample_audio` command to resample the audio from the DV file:

    ```
    python dv_resample_audio.py captured.dv --output captured-audio.mkv --stats captured-audio.csv
    ```

    The output MKV file contains only the audio streams.  The duration of each audio stream precisely matches the duration of the input video stream.

3.  Mux the resampled audio back into the original DV file using FFmpeg:

    ```
    ffmpeg -i captured.mkv -i captured-audio.mkv -map 0 -map -0:a -map 1:a -c:v copy -c:a flac resynced.mkv
    ```

    This command will retain all streams from the `captured.mkv` file _except_ for the audio streams.  For example, the video stream and any chapters that were created by DVRescue will be retained.  Audio streams will instead be muxed in from the `captured-audio.mkv` file that was outputted by dv_resample_audio.  This example also uses the lossless FLAC codec to compress the audio.

4.  Recommended: analyze the output CSV file.  This provides a way to detect whether there have been particularly anomalous issues that were fixed.  A separate set of columns are emitted for each input audio stream.  The columns are:
      - `video_start_frame_number`: the starting video frame number analyzed for this row in the CSV file.
      - `video_frame_count`: the total number of video frames for this row in the CSV file.  The corresponding audio for these video frames is resampled in a single batch and represents a periodic point of synchronization.

        The value is chosen so that an integer number of audio frames will fit in this number of video frames.  For example, 15 NTSC video frames have a duration of 0.5005 seconds, inside of which exactly 16016 32 kHz audio samples will fit inside it.  No fewer video frames can be processed at a time without breaking causing rounding errors in the expected number of audio samples.
      - `audio_n_actual_sample_count`: the total number of audio samples that were actually decoded for these video frames.
      - `audio_n_expected_sample_count`: the total number of audio samples that we would have ideally decoded for these video frames, assuming that the clocks were perfect.
      - `audio_n_diff_sample_count`: subtraction of the previous two values.  Positive values mean that the audio clock ran faster than the video clock (higher-than-advertised audio sample rate), and negative values mean the audio clock was slower than the video clock.  **When you analyze this file, check for excessively large or small values, which would result in audio distortion.**  Values <= 5 should be fine for unlocked audio cameras.  Values of 0 should be expected for locked audio cameras.
      - `audio_n_accumulated_diff_sample_count`: sum of the `audio_n_diff_sample_count` values up to this point.  This represents how far off the audio would be at this point in the video if the video was processed from the beginning by some other software.
      - `audio_n_accumulated_diff_seconds`: value of `audio_n_accumulated_diff_sample_count` converted to seconds using the sample rate.
      - `audio_n_missing_frames`: list of video frame numbers that were completely missing corresponding audio samples.  **When you analyze this file, check for rows that have frames listed here.**  These frames will have silent audio.  Most likely they would also be flagged as having audio errors in DVRescue or DV Analyzer.

## More technical information

The dv_resample_audio script works as follows:

1.  Determine an appropriate number of video frames with corresponding audio samples to process at a time.  The value is chosen to ensure that both video frame count and audio sample count are integers.  This avoids unnecessary resampling due to rounding errors.
2.  For each batch of video frames to process:
    1.  Directly read the video frames for this group from the `.dv` file into a separate buffer.  _This is an extremely critical step to defeat the accumulated clock drift._  It is effectively equivalent to starting playback at a given physical location from the videotape.
    2.  Use FFmpeg to decode only the audio samples from the frames in this in-memory buffer.
        1.  If no audio samples are found for a given video frame, then silence is inserted, and the frame is flagged as a missing frame in the CSV file.
    3.  Resample the audio for this batch so that the number of audio samples _precisely_ matches the expected number.
        1.  If the input was off by very few frames (e.g. 1 or 2), then the audio is simply truncated, or extended with silence at the end.  The remaining audio samples are not modified in any way.
        2.  Larger errors are corrected by resampling using `aresample` in FFmpeg (see [documentation](https://ffmpeg.org/ffmpeg-resampler.html)).
    4.  The resampled audio buffer is written to the output MKV file.

This approach guarantees that audio samples are not modified as much as possible.  It also guarantees that they are locked to the video frames that they were physically interleaved with on the videotape.
