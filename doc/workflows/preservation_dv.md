# DV tape preservation

This procedure is for transferring DV videotape using a FireWire connection on Windows 7 64-bit.  Since FireWire is used, the original video bytes from the tape is transferred mostly as-is byte-for-byte (as opposed to an analog capture).

If necessary, multiple transfers of the tape can be performed in order to eliminate transient errors that don't reliably occur in the same place.  The analysis, merging, and repackaging steps can & should be done on a modern Windows PC (e.g. Windows 10), since they don't require legacy transfer hardware.

The final output of this procedure is a single MKV file that is the result of merging multiple transfer passes.  In addition to the DV data, the MKV file contains demuxed audio that is carefully synchronized to the video, and automatically-created chapters at recording timestamp changes.

Tested equipment:
- Digital8 tape using a Sony DCR-TRV460 camcorder on Windows 7 64-bit

Tested formats:
- DV, NTSC, 4-channel 32 kHz audio (only 2 channels used), unlocked audio, 25 mbps bit rate

In practice, this equipment was used to preserve old home movies.

## Directory organization

Create a directory for holding the intermediate files related to this project.  Files created in this project should generally follow this convention:

- The directory should be named after the tape number added during [intake](intake.md).  For example, a tape that was labeled "Johnston #3" should have a directory named `Johnston3`.
- Initially-transferred files are prefixed with `cap-` to indicate they are initially-captured files, and to reduce the risk of accidental deletion/modification.
- Remaining files are prefixed with `int-` to indicate they are intermediate files on our way to a final preservation file.
- Include a step number as the second component in the filename, i.e. `int-3` is the third step in processing.  If there are multiple capture passes, this is included as a second number.

WARNING:  DVRescue can't reliably handle paths with spaces in them.  Always save files in full paths that don't have spaces.

## Top-level workflow

1.  **Follow the procedure in [Video transfer pass](#video-transfer-pass) to transfer a single copy of the tape.**

2.  **Unpackage the AVI file into a bare DV file.**  (This is because DVRescue merging has challenges with AVI files: it doesn't correctly handle the container headers per MediaInfo, and frames could get truncated if input media is of different lengths).  We will use FFmpeg directly for this, based off the [dvpackager](https://github.com/mipops/dvrescue/blob/8e09e0e2323ce4a41d18bdbdae4f1025780955ef/tools/dvpackager#L894) source code.  (I couldn't figure out how to run the Cygwin environment for using dvpackager directly.)

    Run this command:
    ```
    ffmpeg -i cap-pass-X.avi -map 0:v:0 -c copy -f rawvideo int-1-pass-X.dv
    ```

    Replace `X` with the transfer pass number.  The AVI filename may need to be adjusted based on the auto-generated path from WinDV.

3.  **Perform analysis of the transferred DV file in DVRescue GUI.**
    1.  Go to the **Analysis** portion of DVRescue GUI.  ([Documentation](https://mipops.github.io/dvrescue/sections/analysis.html))
    2.  Click the `+` folder icon and browse to the transferred DV file, `int-1-pass-X.dv`.
    3.  Skim through the special frames of interest to see what we're dealing with.  See the above documentation link to learn the meaning of the icons and columns.
    4.  Use the **Segment** feature to identify how best to trim the transferred tape.  For example, discontinuities in aspect ratio or audio format could be particularly problematic.  For our use case of home videos, this shouldn't be an issue.  Note that the segments identified here won't actually be used yet; we're just figuring out what we want to do for later.

4.  **Perform analysis of the transferred DV file in DV Analyzer.**
    1.  Run DV Analyzer and open the file.
    2.  Skim through the frame list to see what we're dealing with.

5.  **After the first transfer, consider making a second transfer of the tape.**  If the transfer has errors, then consider making a second transfer of the tape.  Repeat the top-level steps from step 1 up to this point.  (NOTE:  The decision whether to transfer more than two times will be made after each merge.)

6.  **Merge all transfer pass files into one DV file.**  If the tape has been transferred multiple times, they must be merged so as to keep only error-free frames.  Preference should be for merging using DVRescue.
    1.  If only one (reasonably) error-free transfer was made, then skip the actual merging step.  Copy the one and only `int-1-pass-1.dv` to `int-1-pass-1.dv_merged.dv` for use later in this procedure.
    2.  Merging using DVRescue:
        1.  Go to the **Merge** portion of DVRescue GUI.  ([Documentation](https://mipops.github.io/dvrescue/sections/merge.html))
        2.  Add the input files to the **Input Files** box using the `+` folder icon button, if they aren't already present.
        3.  Drag all transferred `int-1-pass-X.dv` files to merge into the **Files to Merge** box.  The first file added will be the primary file: pick one that is the most complete and with the fewest DV timecode errors.  Frame data will be copied from the other files as needed into the primary file.
        4.  Choose **Package into same folder**.  The output will be in a `_merged.dv` suffix file.
        5.  Click **Merge** to perform the merge.
        6.  Carefully review the **Summary** table to see the results of merging.  Review documentation to interpret the meaning.
        7.  Open the merged file in the **Analysis** and check the results.  Improvements over the analysis of the individual input files should hopefully be noted.
        8.  Also analyze the merged file in DV Analyzer.  Again, there should be improvements over the individual input file analysis.
    3.  Merging using the ([dv_merge](../tools/dv_merge.md)) tool from this repository:
        1.  Run the `dv_merge` command with all the inputs.  Experiment with both merge algorithms.  Note that all input files must be the same length, and frame numbers must exactly correlate.  See the tool documentation for more information.
        2.  Open the merged file in DVRescue's **Analysis** and check the results.
        3.  Also analyze the merged file in DV Analyzer.
    4.  Merged results may be worse than the inputs.  Some trial & error is necessary.  Merge issues to watch out for:
        1.  DVRescue might drop input frames entirely.
        2.  DVRescue has been observed to replace valid frame data with a duplicate frame when there are timecode inconsistencies.
        3.  dv_merge sometimes inexplicably creates new timecode issues that didn't exist before.
        4.  Always visually inspect the merge results, especially for frames that had errors of some kind.
    5.  _Merging issues seem to stem from timecode issues_ - see [DVRescue #929](https://github.com/mipops/dvrescue/issues/929).  If a transfer pass is available with minimal to no timecode issues detected by DVRescue, then the problem might be helped by using that pass as the first pass in the input list for the merge.  Always carefully check the merge results!

7.  **After merging, consider making an additional transfer of the tape.**  If there are still remaining errors after merging, then consider making an additional transfer of the tape.  Repeat the top-level steps from step 1 up to this point.  This may be especially fruitful if adding the previous transfer as a merge input helped resolve some of the previous errors.  Use the error graph and frame list to get an idea of whether additional transfers beyond the first two would be helpful.

8.  **Package the merged result.**  This will get us a file with chapters and separate audio streams:
    1.  Go to the **Package** portion of DVRescue GUI.  ([Documentation](https://mipops.github.io/dvrescue/sections/packaging.html))
    2.  Add the merged output to **Input Files** if it is not already present, and then click it to highlight it in green.
    3.  Choose appropriate **Segmenting Rules** based on what was learned earlier, and click **Apply**.
    4.  Choose the **mkv** container format.
    5.  Choose **Package into same folder**.
    6.  Click **Add to Queue** and wait for the files to be processed.

9.  **Resample the audio so that it is precisely synchronized with the video frames.**  This will prevent the audio from drifting away from the video over time.  Run the [dv_resample_audio](../tools/dv_resample_audio.md) script:

    ```
    # Unwrap the DV data:
    ffmpeg -i int-1-pass-N.dv_merged_part1.mkv -map 0:v:0 -c copy -f rawvideo int-2-merged.dv

    # Resample the audio
    python dv_resample_audio.py int-2-merged.dv --output int-3-resampled-audio-only.mkv --stats int-3-resampled-audio-only.csv
    ```

    Replace `N` in the first input filename so that it matches the actual DVRescue-packaged merge result.

    1.  Inspect the output CSV file and ensure that `audio_0_diff_sample_count` is never outside of range [-2, 2].
    2.  Also check that `audio_0_missing_frames` is empty everywhere, except for known frames that have 100% audio errors.

10. **Repackage the merged result.**  This will add important colorspace metadata, mux in the resynchronized audio, and compress the PCM audio to FLAC:

    ```
    ffmpeg -field_order bt -color_primaries smpte170m -color_trc smpte170m -colorspace smpte170m -color_range tv -i int-1-pass-N.dv_merged_part1.mkv -i int-3-resampled-audio-only.mkv -map 0 -map -0:a -map 1:a -c:v copy -c:a flac int-4-final-merged.mkv
    ```

    Replace `N` in the first input filename so that it matches the actual DVRescue-packaged merge result.

11. **Check the final output in MediaInfo**.  Open the input `int-1-pass-N.dv_merged.dv`, the intermediate `int-1-pass-N.dv_merged_part1.mkv`, and the final output `int-4-final-merged.mkv` files with MediaInfo.  The main file to examine is the final output, but the other files are useful for comparison to see what changed.  Confirm the following in the final file's output:
    -   **General**
        -   **Format**: Matroska
        -   **Recorded date**: should be present/accurate
    -   **Video**
        -   **Format**: DV
        -   **Codec ID**: V_MS/VFW/FOURCC / dvsd
        -   **Width**: same as input file (for NTSC, 720)
        -   **Height**: same as input file (for NTSC, 480)
        -   **Display aspect ratio**: same as input file (typically 4:3)
        -   **Frame rate mode**: Constant
        -   **Frame rate**: same as input file (for NTSC, 29.970).  NOTE:  The fraction given is typically wrong for NTSC; verify the correct NTSC value of 30000/1001 is shown later on by ffprobe.
        -   **Standard**: same as input file (e.g. NTSC)
        -   **Color space**: YUV
        -   **Chroma subsampling**: same as input file (for NTSC, 4:1:1)
        -   **Bit depth**: 8 bits
        -   **Scan type**: Interlaced
        -   **Scan type, store method**: Interleaved fields (NOTE: this must not be [separated](https://www.mir.com/DMG/interl.html))
        -   **Scan order**: Bottom Field First
        -   **Color range**: Limited
        -   **Color primaries**: for NTSC, BT.601 NTSC
        -   **Transfer characteristics**: BT.601
        -   **Matrix coefficients**: BT.601
    -   **Audio** (FLAC-encoded stream; one stream per pair of input channels)
        -   **Format**: FLAC
        -   **Channel(s)**: 2 channels
        -   **Channel layout**: L R
        -   **Sampling rate**: same as input file
        -   **Bit depth**: 16 bits
        -   **Default**: yes for the first stream, no for the second (if any)
    -   **Audio** (muxed in video)
        -   **Format**: PCM
        -   **Format settings**: Big / Signed
        -   **Muxing mode**: DV
        -   **Channel(s)**: 2 channels
        -   **Sampling rate**: same as input file
        -   **Bit depth**: same as input file
    -   **Menu**
        -   All gaps in the recording time should trigger a new chapter.  The chapter names contain the DV timestamp and the recording timestamp
    -   No conformance errors or other errors are shown anywhere.

12. **Check the final output in ffprobe.**

    ```
    ffprobe -show_streams int-4-final-merged.mkv
    ```

    Confirm the following key subset of metadata in the final output:

    ```
    [STREAM]
    index=0
    codec_name=dvvideo
    codec_type=video
    width=<same as input file; for NTSC, 720>
    height=<same as input file; for NTSC, 480>
    coded_width=<same as input file; for NTSC, 720>
    coded_height=<same as input file; for NTSC, 480>
    sample_aspect_ratio=<same as input file; for NTSC 4:3 display aspect ratio, this is 8:9>
    display_aspect_ratio=<same as input file; typically 4:3>
    pix_fmt=<same as input file; for NTSC, yuv411p>
    color_range=tv
    color_space=<for NTSC, smpte170m>
    color_transfer=<for NTSC, smpte170m>
    color_primaries=<for NTSC, smpte170m>
    chroma_location=<for NTSC, topleft>
    field_order=bt
    r_frame_rate=<same as input file, for NTSC, 30000/1001>
    avg_frame_rate=<same as input file, for NTSC, 30000/1001>
    TAG:DURATION=<make a note of the duration>
    [/STREAM]
    [STREAM]  # repeated for every pair of audio channels
    index=<n>
    codec_name=flac
    codec_type=audio
    sample_fmt=s16
    sample_rate=<same as input file, measured in Hz>
    channels=2
    channel_layout=stereo
    TAG:DURATION=<must match the video stream duration from above within 1 millisecond>
    [/STREAM]
    ```

13. **Check the final output MKV file in MediaConch.**
    1.  **Checker**:
        1.  **Policy**: **No policy**
        2.  **Display**: **MediaConchHtml**
        3.  **Verbosity**: **5**
        4.  **Parse speed**: **Full (1)**
        5.  **Enable fixer**: off
        6.  **Select files**: pick the final `int-4-final-merged.mkv` file.
    2.  Click the **Check files** button.
    3.  Inspect any failures.  None are expected.

14. **Check the final output MKV file in FFmpeg.**  This will decode the entire video.

    ```
    ffmpeg -i int-4-final-merged.mkv -f null -
    ```

15. **Play back the final output MKV file in VLC.**  Open the final `int-4-final-merged.mkv` file in VLC, and check the following:
    -   Plays smoothly with both video and audio.
    -   There are no interlacing artifacts (automatic deinterlacing is selected, no comb artifacts, and no jumpiness from the wrong scan order).  Try turning off interlacing and confirm that the file is still actually interlaced.
    -   The video is sized to the expected display aspect ratio
    -   Compare the appearance of a video frame with the same video frame in the originally-transferred input AVI file, and ensure exactly zero color shift has happened.

16. **Check A/V sync of the output file using the linked [procedure](audio_sync_check.md).**  Audio level changes at scene changes should be extremely precise because of the above audio resampling procedure.  Check several frames throughout.

17. **Rename the final `int-4-final-merged.mkv` file to an appropriate filename.**  (For example, `2000 Christmas.mkv`.)  Move this file to the appropriate long-term archival location.  The original AVI files and intermediate files can now be safely discarded.  (However, you may choose to wait to discard these until after further post-processing.)

18. **Copy the [preservation notes template](templates/dv_preservation_notes.txt) and rename it after the final MKV filename.**  (For example, `2000 Christmas.txt`).  **Fill out the top part of the template regarding preservation notes.**

NOTE: If desired, the second step can always be repeated to unwrap the MKV file back to a bare DV file.  It will be byte-for-byte identical to the DV file used to create the MKV file package.

## Video transfer pass

To transfer a DV videotape, follow these steps.  They may be repeated multiple times for multiple transfer passes.

1.  **Configure the Sony DCR-TRV460 camcorder for playback.**
    1.  Disable all digital effects (Camera Operations Guide page 48).
    2.  Disable all picture effects (Camera Operations Guide page 68).
    3.  Disable magnification (Camera Operations Guide page 53).
    4.  Disable metadata from TV output (Camera Operations Guide page 54 and 81).
    5.  Disable variable speed playback (Camera Operations Guide page 47).
    6.  Set **Multi-Sound** to stereo (Camera Operations Guide page 76).
    7.  Set **PB MODE** to **AUTO** (Camera Operations Guide page 79).

2.  **Prepare the tape for transfer.**  Connect the camcorder to the Windows 7 64-bit computer using a FireWire cable.  Turn it on into tape playback mode.  Insert the tape and rewind it.

3.  **Prepare to transfer video in WinDV.**
    1.  Click the **Capturing from DV device** tab.
    2.  **Video source**: pick the FireWire connection
    3.  **Capt file**: name it with a `cap-pass-X` prefix, where `X` is the capture pass number (starting at 1).  Final filenames are created by WinDV by appending additional metadata.
    4.  Checkbox to the left of the **Capture** button: on.  This checkbox doesn't have a clearly labeled purpose in the software, but the website documents it as: "Enable DV control: If checked, the DV-camcorder or VCR is automatically controlled with the WinDV."
    5.  Click the **Config** button, and then **Capturing from DV device**:
        1.  Pick **type-1 AVI (iavs)**.  This is a smaller file size, without losing any real information.  (Type 2 AVIs will demux/duplicate the audio from the DV data stream into a separate audio channel, which we aren't going to use.)
        2.  **Discontinuity threshold (sec)**: `0`.  A value of `0` will transfer all video into one file.  (Larger values would split into multiple files whenever the DV timestamp has discontinuities).
        3.  **Max AVI size (frames)**: `1000000`.  This is the maximum possible value, and is over 9 hours of NTSC video.  This will prevent arbitrary splits of AVI files to limit maximum file size.
        4.  **Every N-th frame**: `1`.  This will transfer every frame.

5.  **Transfer the tape.**  Click the **Capture** button in WinDV, and transfer the tape.  Click the **Capture** button again to stop capturing at the end of the tape, if it didn't automatically stop.  That will pause the transfer.  Then, click the **Cancel** button to stop transferring.
    -   Note: the **Q** value in the status bar indicates the buffer usage: **0** for empty, **100** for full.  It should stay very close to **0**.

6.  **Transfer the file to your main, modern Windows computer over a network.**
