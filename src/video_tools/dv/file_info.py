"""High-level utility functions for gathering DV file information."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from fractions import Fraction
from typing import BinaryIO

import av.container


class DVSystem(Enum):
    SYS_525_60 = auto()  # 525 signal lines with 29.97 FPS (NTSC)
    SYS_625_50 = auto()  # 625 signal lines with 25.00 FPS (PAL/SECAM)


# Map of DIF sequence count within a frame to the corresponding DVSystem
# SMPTE 306M-2002 Section 11.2 Data Structure
# IEC 61834-2 Section 11.2 Data Structure
DIF_SEQUENCE_COUNT_TO_SYSTEM = {
    10: DVSystem.SYS_525_60,
    12: DVSystem.SYS_625_50,
}


@dataclass(frozen=True, kw_only=True)
class DVFileInfo:
    """Contains top-level DV file information."""

    file_size: int  # bytes

    video_frame_rate: Fraction  # frames per second
    video_duration: Fraction  # duration of entire video stream, in seconds
    video_frame_count: int
    video_frame_size: int

    # 1 for 25 mbps, 2 for 50 mbps:
    video_frame_channel_count: int
    # 10 for NTSC (30 fps), 12 for PAL/SECAM (25 fps):
    video_frame_dif_sequence_count: int

    audio_stereo_channel_count: int
    audio_sample_rate: int | None  # Hz; only None if audio channel count is 0

    def audio_samples_per_frame(self) -> Fraction:
        # We want to resample the audio that was stored with a video frame to the correct
        # number of audio samples for that video frame, since there could actually be too
        # few or too many.  However, there's usually a non-integer ideal number of audio
        # samples expected in each single video frame.  This function returns the integer
        # number of video frames required to have an integer ideal number of audio samples.
        # See https://www.adamwilt.com/DV-FAQ-tech.html#LockedAudio
        #
        # For example, NTSC is at 30000/1001 video frame rate, and might have 32 kHz audio.
        # Every 15 video frames will have 16016 audio samples; we can't have an integer
        # number of audio samples for any fewer amount of video frames.
        #
        # This function returns a Fraction: the numerator is a number of audio samples, and
        # the denominator is the number of video frames for those audio samples.
        if self.audio_sample_rate is None:
            raise ValueError("No audio channels to analyze.")
        return self.audio_sample_rate / self.video_frame_rate

    def assert_similar(self, other: DVFileInfo) -> None:
        """Assert that the audio format has not changed."""
        assert self.video_frame_rate == other.video_frame_rate
        assert self.video_frame_size == other.video_frame_size
        assert self.audio_stereo_channel_count == other.audio_stereo_channel_count
        assert self.audio_sample_rate == other.audio_sample_rate

    @property
    def system(self) -> DVSystem:
        return DIF_SEQUENCE_COUNT_TO_SYSTEM[self.video_frame_dif_sequence_count]


def read_dv_file_info(file: BinaryIO) -> DVFileInfo:  # type: ignore[return]
    # read top-level information
    with av.container.open(file, mode="r", format="dv") as input:
        assert len(input.streams.video) == 1
        file_size = input.size

        video_frame_rate = input.streams.video[0].base_rate
        # Make sure we got exact NTSC or PAL/SECAM frame rate
        assert video_frame_rate == Fraction(30000, 1001) or video_frame_rate == Fraction(25)

        assert input.duration is not None
        video_duration = Fraction(input.duration, 1000000)

        # duration was in microseconds, and still lacked precision, so we round it
        video_frame_count = round(video_frame_rate * video_duration)

        # Every video frame uses the exact same number of bytes in a raw DV file
        video_frame_size = int(file_size / video_frame_count)
        assert video_frame_size * video_frame_count == file_size
        # We only support 25 mbps or 50 mbps files at this time.
        # 525/60 at 25 mbps: 1 channel * 10 sequences * 150 DIF blocks/seq * 80 bytes/DIF block
        # 625/50 at 25 mbps: 1 channel * 12 sequences * 150 DIF blocks/seq * 80 bytes/DIF block
        # 50 mbps: the same calculations as above but with 2 channels
        # See ITU-R BT.1618-1 Annex 1, 1.2 Data structure
        if video_frame_size == 1 * 10 * 150 * 80:
            video_frame_channel_count = 1
            video_frame_dif_sequence_count = 10
        elif video_frame_size == 1 * 12 * 150 * 80:
            video_frame_channel_count = 1
            video_frame_dif_sequence_count = 12
        elif video_frame_size == 2 * 10 * 150 * 80:
            video_frame_channel_count = 2
            video_frame_dif_sequence_count = 10
        elif video_frame_size == 2 * 12 * 150 * 80:
            video_frame_channel_count = 2
            video_frame_dif_sequence_count = 12
        else:
            raise ValueError(f"Unsupported frame size {video_frame_size}")

        # Make sure it's a known audio format
        audio_stereo_channel_count = len(input.streams.audio)
        assert (
            # DVCPRO50 at https://archive.org/details/SMPTEColorBarsBadTracking has no audio...
            # So zero audio channels is definitely a thing.
            audio_stereo_channel_count == 0
            or audio_stereo_channel_count == 1
            or audio_stereo_channel_count == 2
        )
        audio_sample_rate = (
            input.streams.audio[0].sample_rate if audio_stereo_channel_count > 0 else None
        )
        assert (
            audio_sample_rate is None
            or audio_sample_rate == 32000
            or audio_sample_rate == 44100
            or audio_sample_rate == 48000
        )
        for audio_stream in input.streams.audio:
            assert audio_stream.sample_rate == audio_sample_rate
            assert audio_stream.format.name == "s16"
            assert audio_stream.layout.name == "stereo"
            assert audio_stream.channels == 2
            assert audio_stream.rate == audio_sample_rate

        return DVFileInfo(
            file_size=file_size,
            video_frame_rate=video_frame_rate,
            video_duration=video_duration,
            video_frame_count=video_frame_count,
            video_frame_size=video_frame_size,
            video_frame_channel_count=video_frame_channel_count,
            video_frame_dif_sequence_count=video_frame_dif_sequence_count,
            audio_stereo_channel_count=audio_stereo_channel_count,
            audio_sample_rate=audio_sample_rate,
        )
