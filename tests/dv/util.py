from dataclasses import replace
from fractions import Fraction

import video_tools.dv.file_info as dv_file_info

SIMPLE_FILE = dv_file_info.DVFileInfo(
    file_size=5 * 10 * 150 * 80,
    video_frame_rate=Fraction(30000, 1001),
    video_duration=Fraction(30000, 1001) / 5,
    video_frame_count=5,
    video_frame_size=10 * 150 * 80,
    video_frame_channel_count=0,
    video_frame_dif_sequence_count=10,
    audio_stereo_channel_count=4,
    audio_sample_rate=32000,
)

NTSC_FILE = replace(
    SIMPLE_FILE,
    video_frame_rate=Fraction(30000, 1001),
    video_duration=Fraction(30000, 1001) / 5,
    video_frame_dif_sequence_count=10,
)

PAL_FILE = replace(
    SIMPLE_FILE,
    video_frame_rate=Fraction(25, 1),
    video_duration=Fraction(25, 1) / 5,
    video_frame_dif_sequence_count=12,
)
