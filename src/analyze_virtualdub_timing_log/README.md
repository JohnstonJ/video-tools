# analyze_virtualdub_timing_log

When capturing AVI files, VirtualDub can create a timing log.  This script flags any video and audio frames that have particularly anomalous timestamps.  These locations in the AVI file can then be manually examined in more detail.

To use this script:

1.  Before capturing an AVI file in VirtualDub, click the **Capture** menu, and then toggle on **Enable timing log**.
2.  Start the capture as normal.
3.  When the capture finishes, VirtualDub will ask you to save the CSV file for the timing log.
4.  Run the `analyze_virtualdub_timing_log.py` script, using this timing log as input.  You will also need to provide the exact frame rate of the AVI file as input.  The following example applies for NTSC 29.970 frame rates:

	```
	python analyze_virtualdub_timing_log.py --fps-num 30000 --fps-den 1001 MyTimings.csv
	```

5.  The script will print out all video and audio frames that have timings that look a little too far off.  Carefully check the video at and around these global time positions for:
    - Null/drop video frames (i.e. inserted/repeated frames).
    - Incorrect audio/video sync.
    - Unexpected video frame data.
    - Audio distortion.
