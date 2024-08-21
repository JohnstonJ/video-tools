# video-tools
Contains tools and workflows for restoring video files using Avisynth, VirtualDub, and other tools.

## Initial setup

Create and activate a Python virtual environment.  For example, on Windows from the Command Prompt:

```
<path_to>\python.exe -m venv .\.venv
.\Scripts\activate.bat
```

Next, install the package locally for development:

```
pip install --editable .[dev]
```

Or build a wheel:

```
pip install --upgrade build
python -m build
```

When running some tools, note that you must also ensure that FFmpeg is in your `PATH`, if it is not already.

## Workflows

See the [README](doc/workflows/README.md) for more information on preservation and video restoration procedures.

## List of tools

- [analyze_virtualdub_timing_log](doc/tools/analyze_virtualdub_timing_log.md) analyzes timing logs from VirtualDub that are recorded while capturing AVI files.  Frames with anomalous timestamps are flagged for manual investigation.
- [dv_merge](doc/tools/dv_merge.md) is an experimental tool for merging raw DV video files from multiple capture passes.
- [dv_resample_audio](doc/tools/dv_resample_audio.md) resamples DV audio so that it is locked to the video frames that it was interleaved with.  This corrects audio drift that is present from unlocked DV cameras, such as consumer camcorders.
- [top_line_errors](doc/tools/top_line_errors.md) uses the Avisynth SpotLess filter to identify frames that have VHS dropouts.  The script then writes a list of affected frame numbers to a text file, so that later an Avisynth script can selectively run the filter only on affected frames.
