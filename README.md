# video-tools
Contains tools for scanning video files for information in conjunction with Avisynth and VirtualDub workflows.

## Initial setup

Create and activate a Python virtual environment.  For example, on Windows from the Command Prompt:

```
<path_to>\python.exe -m venv .\.venv
.\Scripts\activate.bat
```

Next, install the requirements:

```
pip install -r requirements.txt
```

Note that you must also ensure that FFmpeg is in your PATH, if it is not already.

You can now run the scripts in this repository.

## List of tools

- [analyze_virtualdub_timing_log](src/analyze_virtualdub_timing_log/README.md) analyzes timing logs from VirtualDub that are recorded while capturing AVI files.  Frames with anomalous timestamps are flagged for manual investigation.
- [dv_merge](src/dv_merge/README.md) is an experimental tool for merging raw DV video files from multiple capture passes.
- [dv_resample_audio](src/dv_resample_audio/README.md) resamples DV audio so that it is locked to the video frames that it was interleaved with.  This corrects audio drift that is present from unlocked DV cameras, such as consumer camcorders.
- [top_line_errors](src/top_line_errors/README.md) uses the Avisynth SpotLess filter to identify frames that have VHS dropouts.  The script then writes a list of affected frame numbers to a text file, so that later an Avisynth script can selectively run the filter only on affected frames.
