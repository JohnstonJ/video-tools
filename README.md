# video-tools
Contains tools and workflows for restoring video files using Avisynth, VirtualDub, and other tools.

## Initial setup

Create and activate a Python virtual environment.  For example, on Windows from the Command Prompt:

```
<path_to>\python.exe -m venv .\.venv
.\Scripts\activate.bat
```

Next, install the package locally:

```
pip install .
```

When running some tools, note that you must also ensure that FFmpeg is in your `PATH`, if it is not already.

### Development setup

To develop this Python project, first start with the activated virtual environment you previously created.

```
pip install --editable .[dev]
```

# TODO is it true i have to recompile ?  also can i skip mypyc completely?
Note that this command will also recompile the C extension using [mypyc](https://mypyc.readthedocs.io/), so this must be rerun whenever Python code has been modified.

To run verifications, first install Nox:

```
pip install --upgrade nox
```

And then run them.

```
nox -s verify
```

Running nox without arguments will verify, and then build the distribution wheel:

```
nox
```

To reformat code:

```
nox -s format
```

Don't forget you can add the `-R` parameter to nox if you want to reuse existing virtual environments to save time.

#### Visual C++ dependency

This project makes use of [mypyc](https://mypyc.readthedocs.io/), which requires a Visual C++ compiler on Windows.  The easiest path would be to install Visual C++ if necessary when prompted during the build.  However, a portable version of Visual C++ can also be used:

1.  Use [PortableBuildTools](https://github.com/Data-Oriented-House/PortableBuildTools) to download a portable copy of Visual C++.  The default settings should be fine.
2.  Open a terminal with Command Prompt or PowerShell 7.  Note that Windows PowerShell 5.1 is not supported by PortableBuildTools.
2.  Run `devcmd.bat` or `devcmd.ps1`, as appropriate for your shell.  This will prepare the environment variables for compiling.
4.  Set the `DISTUTILS_USE_SDK` environment variable to `1`, as recognized by Python [distutils](https://github.com/pypa/distutils/blob/29debe531dcdddc456be42a62dbac837ee0ccfa0/distutils/_msvccompiler.py#L146).  This will instruct it not to try to find an installed Visual C++, and just use the environment instead.
5.  You can now run the above `nox` commands as normal, and they will be able to find Visual C++.

Note that the compiled binaries dynamically link to the Visual C++ runtime, so you may need to install the appropriate Visual C++ redistributable if you don't already have it.

To integrate the linting tools with VS Code:

1.  Install the Ruff extension for VS Code.  Note it will use its own bundled copy of Ruff.
2.  Go to `.vscode/settings.json` for the project and add:
    ```
    {
      "[python]": {
          "editor.formatOnSave": true,
          "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        },
        "editor.defaultFormatter": "charliermarsh.ruff"
      }
    }
    ```
3.  Install the Mypy Type Checker for VS Code.  Again, note it will use its own bundled copy of mypy.

## Workflows

See the [README](doc/workflows/README.md) for more information on preservation and video restoration procedures.

## List of tools

- [analyze_virtualdub_timing_log](doc/tools/analyze_virtualdub_timing_log.md) analyzes timing logs from VirtualDub that are recorded while capturing AVI files.  Frames with anomalous timestamps are flagged for manual investigation.
- [dv_merge](doc/tools/dv_merge.md) is an experimental tool for merging raw DV video files from multiple capture passes.
- [dv_repair](doc/tools/dv_repair.md) can be used to repair errors in a DV file, such as subcode incoherencies.
- [dv_resample_audio](doc/tools/dv_resample_audio.md) resamples DV audio so that it is locked to the video frames that it was interleaved with.  This corrects audio drift that is present from unlocked DV cameras, such as consumer camcorders.
- [top_line_errors](doc/tools/top_line_errors.md) uses the Avisynth SpotLess filter to identify frames that have VHS dropouts.  The script then writes a list of affected frame numbers to a text file, so that later an Avisynth script can selectively run the filter only on affected frames.
