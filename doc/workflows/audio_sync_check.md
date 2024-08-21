# Checking audio/video sync

If there's a question about whether audio and video is in sync within a video, the best thing to do is view the audio and video frame by frame in VirtualDub2:

1.  Open the movie file in VirtualDub2.
    -   If checking for change in the A/V sync of an intermediate/processed file, then also open the original input file in a second VirtualDub2 instance for comparison.  Repeat these steps in each VirtualDub2 instance.
2.  Click **View**: **Audio display** to turn on audio waveforms.
    -   NOTE: VirtualDub2 allows you to double-click in the audio display to navigate frames.  The original VirtualDub does not.
3.  Look for locations in the video where the audio and video significantly change at the exact same moment.  Then, make sure that the audio sharply transitions at that point.  If comparing with a processed file, go to the same frame number and compare.
    -   A good example of this is a scene change where there is also a major change in audio levels.

When comparing many locations across several different files (such as when merging multiple analog captures), it's helpful to take notes.  For each file, note each frame number that was inspected, and how far off (and which direction) the sound was vs the video.  This allows one to quickly recheck the sound on future files (either after further processing, or from an additional capture pass).
