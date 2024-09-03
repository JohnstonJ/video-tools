"""Classes for parsing DV DIF blocks."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

import video_tools.dv.file.info as dv_file_info
from video_tools.dv.block.base import Block, BlockError, BlockID, Type
from video_tools.dv.block.binary_types import _HeaderBinaryFields


# Track pitch
# IEC 61834-1:1998 Section 6.4 - TIA (track information area)
# IEC 61834-1:1998 Amendment 1 - LP mode (long play mode with narrow track pitch)
class TrackPitch(Enum):
    # Standard play defined in IEC 61834-1.  The track pitch is actually 10 um on DV tapes.  For
    # other physical formats (e.g. Digital8), this still means standard play, but the track pitch
    # is different.
    STANDARD_PLAY = 0x3

    # Other track pitches are not 10 um.  In practice, it probably means some form of long play.

    # My Sony DCR-TRV460 records long play with this value.  I can't find the relevant standard
    # documentation in the IEC long play amendment that says to use this value, so I found it
    # experimentally.
    LONG_PLAY = 0x2

    # Defined in: SMPTE 306M-2002 Table 17 - Application ID of track information
    D7_STANDARD_FORMAT = 0x1

    RESERVED_TRAC_PITCH_3 = 0x0


# Track application ID (APT)
class ApplicationIDTrack(Enum):
    # Defined in: IEC 61834-1:1998 Table 14 - Application ID of a track in TIA
    CONSUMER_DIGITAL_VCR = 0x0

    # Defined in: SMPTE 306M-2002 Table 17 - Application ID of track information
    D7_STANDARD_FORMAT = 0x1

    # Reserved application IDs may not be safe or possible to process with this tool,
    # because the data layouts could be dramatically different from the above standards
    # that we support.
    RESERVED_2 = 0x2
    RESERVED_3 = 0x3
    RESERVED_4 = 0x4
    RESERVED_5 = 0x5
    RESERVED_6 = 0x6


# Area 1 application ID (AP1)
class ApplicationID1(Enum):
    # Defined in: IEC 61834-2:1998 Table 4 - Application ID of area 1 (AP1)
    CONSUMER_DIGITAL_VCR = 0x0

    # Defined in: SMPTE 306M-2002 Table 26 - Audio application ID
    D7_STANDARD_FORMAT = 0x1

    # Reserved application IDs may not be safe or possible to process with this tool,
    # because the data layouts could be dramatically different from the above standards
    # that we support.
    RESERVED_2 = 0x2
    RESERVED_3 = 0x3
    RESERVED_4 = 0x4
    RESERVED_5 = 0x5
    RESERVED_6 = 0x6


# Area 2 application ID (AP2)
class ApplicationID2(Enum):
    # Defined in: IEC 61834-2:1998 Table 9 - Application ID of area 2 (AP2)
    CONSUMER_DIGITAL_VCR = 0x0

    # Defined in: SMPTE 306M-2002 Table 31 - Video application ID
    D7_STANDARD_FORMAT = 0x1

    # Reserved application IDs may not be safe or possible to process with this tool,
    # because the data layouts could be dramatically different from the above standards
    # that we support.
    RESERVED_2 = 0x2
    RESERVED_3 = 0x3
    RESERVED_4 = 0x4
    RESERVED_5 = 0x5
    RESERVED_6 = 0x6


# Area 3 application ID (AP3)
class ApplicationID3(Enum):
    # Defined in: IEC 61834-2:1998 Table 10 - Application ID of area 3 (AP3)
    CONSUMER_DIGITAL_VCR = 0x0

    # Defined in: SMPTE 306M-2002 Table 33 - Subcode application ID
    D7_STANDARD_FORMAT = 0x1

    RESERVED_2 = 0x2
    RESERVED_3 = 0x3
    RESERVED_4 = 0x4
    RESERVED_5 = 0x5
    RESERVED_6 = 0x6


# DIF header block
# Standards:
#  - IEC 61834-2:1998 Section 11.4.2 - Data part - Header section
#  - IEC 61834-2:1998 Figure 67 - Data in the header section
#  - IEC 61834-2:1998 Table B.3 - Method of transmitting and recording data of header DIF block
#  - SMPTE 306M-2002 Section 11.2.2.1 / Table 56 - Header section
# Important notes:
#  - There is only one header block per DIF sequence/track.
#  - Values are expected to be the same across all DIF sequences/tracks in the same video frame.
@dataclass(frozen=True, kw_only=True)
class Header(Block):
    # DIF sequence flag indicating how many DIF sequences in a video frame.  Each sequence is a
    # tape track and the terminology is basically synonymous.
    # Important notes:
    #  - Not stored on tape / is exclusive to the digital interface.  Errors are not expected.
    video_frame_dif_sequence_count: int  # 10 is 525-60 system, 12 is 625-50 system

    # Track information area: defines low-level information about the physical tape dimensions.
    #  - IEC 61834-2:1998 Table 39 - TIA data in the header section
    #  - IEC 61834-1:1998 Section 4.3.1 - Basic system data
    #  - IEC 61834-1:1998 Section 6.4 - TIA (track information area)
    #  - IEC 61834-1:1998 Section 5.4 - Track F0, track F1, track F2 (discusses pilot signals)
    #  - IEC 61834-2:1998 Figure 5 / 6 - Frames and tracks (shows pilot frames)
    #  - SMPTE 306M-2002 Section 6 - Program track data
    # Important notes:
    #  - The data is read from the tape, so it may be wrong or missing.  Both values must be
    #    either present or absent.
    #  - The track pitch should be constant, based on the selected record mode of the camera.
    #  - The pilot frame will either stay constant, or alternate between frames.  SMPTE 306M-2002
    #    shows several diagrams of varying possibilities.  Whether it's constant or alternating
    #    should stay consistent.
    #  - All values are the same for all DIF sequences/tracks within a single video frame.
    track_pitch: TrackPitch | None
    pilot_frame: int | None

    # Track application numbers: defines the data structure of track areas within a track.
    #  - IEC 61834-1:1998 Section 4 - System data
    #  - IEC 61834-1:1998 Section 6.4 - TIA (track information area)
    #  - IEC 61834-1:1998 Table 14 - Application ID of a track in TIA
    # Important notes:
    #  - The data is read from the tape, so it may be wrong or missing.
    #  - The value should stay constant throughout the recording.
    application_id_track: ApplicationIDTrack | None

    # Area application numbers: defines the data structure within areas of a track.
    #  - IEC 61834-1:1998 Section 4 - System data
    #  - IEC 61834-2:1998 Tables 4 / 9 / 10 - Application ID of area n (APn)
    # Important notes:
    #  - The data is read from the tape, so it may be wrong or missing.
    #  - The value should stay constant throughout the recording.
    application_id_1: ApplicationID1 | None
    application_id_2: ApplicationID2 | None
    application_id_3: ApplicationID3 | None

    def validate(self, file_info: dv_file_info.Info) -> str | None:
        """Indicate whether the contents of the block are valid and could be written to binary.

        The function must not return validation failures that are the likely result of tape
        read errors that resulted in data corruption.  Failures should be the result of logic errors
        on our end / the end-users end, or due to DV data that is normally 100% reliable (i.e. part
        of the digital interface and not subject to tape errors).

        The return value contains a description of the validation failure.  If the block passes
        validation, then None is returned.
        """
        if self.video_frame_dif_sequence_count != 10 and self.video_frame_dif_sequence_count != 12:
            return "DIF header block must specify sequence count of 10 or 12."

        if (
            self.video_frame_dif_sequence_count == 10
            and file_info.system == dv_file_info.DVSystem.SYS_625_50
        ) or (
            self.video_frame_dif_sequence_count == 12
            and file_info.system == dv_file_info.DVSystem.SYS_525_60
        ):
            return f"DIF header block does not match with expected system {file_info.system.name}."

        if (self.track_pitch is not None and self.pilot_frame is None) or (
            self.track_pitch is None and self.pilot_frame is not None
        ):
            return "Track pitch and pilot frame must be both present or absent together."

        if self.pilot_frame is not None and (self.pilot_frame < 0 or self.pilot_frame > 1):
            return "DIF header block must specify a pilot frame of 0 or 1."

        return None

    # Functions for going to/from binary blocks

    @classmethod
    def block_type(cls) -> Type:
        return Type.HEADER

    @classmethod
    def _do_parse_binary(
        cls, block_bytes: bytes, block_id: BlockID, file_info: dv_file_info.Info
    ) -> Header:
        bin = _HeaderBinaryFields.from_buffer_copy(block_bytes[3:])

        # We make several assertions here based on reserved/constant bits.  If the assertions fail,
        # we should investigate more to find out why this is.  Note that it's not expected to be
        # a failure due to tape reading errors.
        if bin.zero != 0x0:
            raise BlockError("Zero bit in DIF header block is unexpectedly not zero.")
        if (
            bin.reserved_0 != 0x3F
            or bin.reserved_1 != 0x01
            or bin.reserved_2 != 0x0F
            or bin.reserved_3 != 0x0F
            or bin.reserved_4 != 0x0F
            or any(r != 0xFF for r in bin.reserved_end)
        ):
            raise BlockError("Reserved bits in DIF header block are unexpectedly in use.")

        if bin.dftia == 0xF:
            track_pitch = None
            pilot_frame = None
        elif bin.dftia > 0x7:
            raise BlockError(
                "Unexpected values in the track information area of the DIF header block."
            )
        else:
            track_pitch = TrackPitch(bin.dftia >> 1)
            pilot_frame = bin.dftia & 0x1

        # Non-zero TFn means that area n is not transmitted.  In practice, I have not seen this
        # ever happen, even during complete frame dropouts.  We need to study an example DV file
        # before can safely remove this assertion and actually do something with these flags.
        if bin.tf1 != 0 or bin.tf2 != 0 or bin.tf3 != 0:
            raise BlockError(
                "Transmitting flags for some DIF blocks are off in the DIF header block."
            )

        return cls(
            block_id=block_id,
            video_frame_dif_sequence_count=12 if bin.dsf == 1 else 10,
            track_pitch=track_pitch,
            pilot_frame=pilot_frame,
            application_id_track=ApplicationIDTrack(bin.apt) if bin.apt != 0x7 else None,
            application_id_1=ApplicationID1(bin.ap1) if bin.ap1 != 0x7 else None,
            application_id_2=ApplicationID2(bin.ap2) if bin.ap2 != 0x7 else None,
            application_id_3=ApplicationID3(bin.ap3) if bin.ap3 != 0x7 else None,
        )

    def _do_to_binary(self, file_info: dv_file_info.Info) -> bytes:
        bin = _HeaderBinaryFields(
            dsf=0x1 if self.video_frame_dif_sequence_count == 12 else 0x0,
            zero=0x0,
            reserved_0=0x3F,
            dftia=(
                0xF
                if self.track_pitch is None or self.pilot_frame is None
                else (self.track_pitch.value << 1) | self.pilot_frame
            ),
            reserved_1=0x1,
            apt=self.application_id_track.value if self.application_id_track is not None else 0x7,
            tf1=0x0,
            reserved_2=0xF,
            ap1=self.application_id_1.value if self.application_id_1 is not None else 0x7,
            tf2=0x0,
            reserved_3=0xF,
            ap2=self.application_id_2.value if self.application_id_2 is not None else 0x7,
            tf3=0x0,
            reserved_4=0xF,
            ap3=self.application_id_3.value if self.application_id_3 is not None else 0x7,
            reserved_end=(ctypes.c_uint8 * 72)(*[0xFF] * 72),
        )
        return bytes([*self.block_id.to_binary(file_info), *bytes(bin)])
