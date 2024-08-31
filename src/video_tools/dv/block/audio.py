from __future__ import annotations

import ctypes
from collections import defaultdict
from dataclasses import dataclass
from typing import ClassVar

import video_tools.dv.file.info as dv_file_info
import video_tools.dv.pack as pack

from .base import Block, BlockID, BlockType


# DIF audio block
# Standards on how audio data is packaged in the digital interface:
#  - IEC 61834-2:1998 Section 11.4.2 - Data part - Audio section
#  - IEC 61834-2:1998 Figure 70 - Data in the audio section
#  - IEC 61834-2:1998 Table 42 - DIF blocks and audio data-sync blocks
#  - IEC 61834-2:1998 Table B.6 - Method of transmitting and recording data of AAUX
#  - SMPTE 306M-2002 Section 11.2.2.4 - Audio section
# Standards on the formatting of the audio blocks themselves:
#  - IEC 61834-2:1998 Section 3.3 - Audio sector
#  - IEC 61834-2:1998 Figure 7 - Structure of sync blocks in audio sector
#  - IEC 61834-2:1998 Section 6 - Audio signal processing
#  - IEC 61834-2:1998 Figures 17/18 - Sample to data bytes conversion for 16 / 12 bits
#  - IEC 61834-2:1998 Table 14 - The construction of an audio block
#  - Many tables and figures relate to Section 6 - only the most important to us are listed here.
#  - IEC 61834-2:1998 Section 9.3 - Main area and optional area
#  - IEC 61834-2:1998 Section 9.4 - AAUX (System data)
#  - IEC 61834-2:1998 Figure 49 - Arrangement of AAUX packs in audio sector
#  - IEC 61834-2:1998 Table 31 - AAUX data of the main area
#  - IEC 61834-4:1998 - entire standard
#  - SMPTE 306M-2002 Section 6.3.3.4 - Composed audio data
#  - SMPTE 306M-2002 Section 7 - Audio processing
# Important notes:
#  - Each tape track physically holds 9 audio blocks in a dedicated area of the tape track.
#  - An audio DIF block consists of two sections: a 5-byte pack known as AAUX, and the remaining 72
#    bytes consists of PCM audio samples.
#  - Within a single video frame, audio is divided into two audio blocks.  The first audio block
#    consists of the first half of the DIF sequences/tracks in a video frame, and the second audio
#    block consists of the remainder of the DIF sequences in the frame.  An audio block consists
#    of one or more audio channels.  Note that for higher bit rate DV formats, additional audio
#    blocks are included, but each audio block remains the same size of 5 or 6 tracks.
#  - AAUX SOURCE and AAUX SOURCE CONTROL packs are supposed to stay the same within an audio block.
#    But they can be different between the two audio blocks.
#  - Audio sample data encoding:
#    - 16-bit signed samples are simply encoded in big endian order in the obvious way.  IEC 61834-2
#      only defines one audio channel will exist within the audio block.
#    - 12-bit signed samples are used for when 2 32 kHz channels are used in an audio block as
#      defined by IEC 61834-2.  A single 12-bit sample from each channel is encoded into 3 bytes
#      as seen in IEC 61834-2:1998 Figure 18:
#      - The first byte is the most significant 8 bits from the first channel's sample.
#      - The second byte is the most significant 8 bits from the second channel's sample.
#      - The third byte consists of the least significant 4 bits from the first channel in the
#        third byte's most significant bits, followed by the least significant 4 bits from the
#        second channel's sample.
#  - If a channel is unused, then IEC 61834-2:1998 Section 6.9 - Invalid recording, states that
#    recording mode in AAUX should be set as 0x7, or INVALID.  Alternatively, audio from the
#    first audio block may be duplicated.
#  - Unused space at the end of the audio data (e.g. when using lower sample frequencies) could
#    contain any undefined value.
#  - Consecutive audio samples are shuffled non-consecutively across various blocks, per
#    IEC 61834-2 Section 6.7 Shuffling method.  Notably, however, within a given DIF block, the
#    audio samples never go backwards in time.  In other words, unused space for audio samples will
#    always be at the end of a given DIF block.
#  - Error handling:
#    - Individual AAUX packs are supposed to be turned into NO INFO packs if errors are detected
#      within the pack.
#    - If errors are detected in the audio samples, those samples are replaced by a special
#      audio error code placeholder value as described in IEC 61834-2:1998 Section 6.4.3.  Those
#      values are 0x8000 for 16-bit samples, and 0x800 for 12-bit samples.
#    - All data is protected by separate error correction codes (not transmitted over DIF).
#
# Special commentary on difference in audio error identification vs DVRescue / MediaInfoLib:
# The DVRescue project notes that some tape decks might not comply with the standard on correctly
# identifying audio samples with the error sample per IEC 61834-2:1998 Section 6.4.3.  Instead,
# they posted samples DV files showing random repeating audio samples:
# https://github.com/mipops/dvrescue/issues/418
# Interestingly, audio is not the only major problem here when I load the files into DVRescue - the
# _video_ data has also not been tagged with STA bits identifying video frame errors, and DVRescue
# does not identify this - even though there are obvious signs of concealment.  What's more, the
# merged MediaInfoLib code does not correctly identify _all_ audio DIF blocks as being in error
# that show this repeating pattern.  It's not 100% clear to me that this is truly a tape deck issue,
# as opposed to an "error" that was correctly written to the tape: multiple capture passes and
# bitwise comparison would conclusively prove whether it's the deck incorrectly (not) identifying
# errors, or if the tape was actually written with that repeating audio/video data.
#
# For the time being, this package will only identify audio samples that are correctly identified
# as an error per IEC 61834-2:1998 Section 6.4.3.  Only if multiple capture passes show potential
# for improvement will it make sense to handle this kind of repeating data.  Furthermore, a
# generalized approach that can handle repeating video frame data in a similar manner to repeating
# audio data should be taken: for example, generically noting that the contents of a DIF block are
# being repeated from frame to frame.
@dataclass(frozen=True, kw_only=True)
class Audio(Block):
    # Parsed pack; will be None if there is a pack parse error due to tape errors.
    pack_data: pack.Pack | None
    # Pack type header values: this is purely informational when reading, and is not used
    # at all when writing audio blocks back out to binary.  It's useful to know what pack type
    # failed to be read if the above packs[n] element is None.
    pack_type: int

    # Raw audio samples
    audio_data: bytes  # always 72 bytes

    def validate(self, file_info: dv_file_info.Info) -> str | None:
        if self.block_id.dif_block < 0 or self.block_id.dif_block > 8:
            return "Unexpected number of DIF blocks in DIF sequence; expected 9."

        assert len(self.audio_data) == 72

        return None

    def has_audio_errors(
        self,
        file_info: dv_file_info.Info,
        frame_sample_count: int,
        quantization: pack.AudioQuantization,
    ) -> bool:
        """Indicates whether the audio data contains any errors, unrelated to the pack."""
        # Get corresponding overall audio sample numbers for this DIF block
        sample_numbers = _sample_positions_to_numbers[file_info.video_frame_dif_sequence_count][
            _BlockPosition(
                dif_sequence_offset=(
                    self.block_id.dif_sequence % (int(file_info.video_frame_dif_sequence_count / 2))
                ),
                dif_block=self.block_id.dif_block,
            )
        ]
        data = self.audio_data
        match quantization:
            case pack.AudioQuantization.LINEAR_16_BIT:
                for block_sample_pos in range(int(72 / 2)):
                    overall_sample_number = sample_numbers[block_sample_pos]
                    if overall_sample_number >= frame_sample_count:
                        break

                    msb = data[2 * block_sample_pos]
                    lsb = data[2 * block_sample_pos + 1]
                    if msb == 0x80 and lsb == 0x00:
                        return True
            case pack.AudioQuantization.NONLINEAR_12_BIT:
                for block_sample_pos in range(int(72 / 3)):
                    overall_sample_number = sample_numbers[block_sample_pos]
                    if overall_sample_number >= frame_sample_count:
                        break

                    msb_y = data[3 * block_sample_pos]
                    msb_z = data[3 * block_sample_pos + 1]
                    lsb = data[3 * block_sample_pos + 2]
                    if (msb_y == 0x80 and lsb & 0xF0 == 0x00) or (
                        msb_z == 0x80 and lsb & 0x0F == 0x00
                    ):
                        return True
            case _:
                assert False
        return False

    # Functions for going to/from binary blocks

    type: ClassVar[BlockType] = BlockType.AUDIO

    @classmethod
    def _do_parse_binary(
        cls, block_bytes: bytes, block_id: BlockID, file_info: dv_file_info.Info
    ) -> Audio:
        bin = _BinaryFields.from_buffer_copy(block_bytes[3:])

        return cls(
            block_id=block_id,
            pack_data=pack.parse_binary(bin.pack, file_info.system),
            pack_type=bin.pack[0],
            audio_data=bytes(bin.data),
        )

    def _do_to_binary(self, file_info: dv_file_info.Info) -> bytes:
        bin = _BinaryFields(
            pack=(ctypes.c_uint8 * 5)(
                *(
                    self.pack_data.to_binary(file_info.system)
                    if self.pack_data is not None
                    # Send a NO INFO pack if we are missing a pack (e.g. from a previous
                    # read error).
                    else pack.NoInfo().to_binary(file_info.system)
                )
            ),
            data=(ctypes.c_uint8 * 72)(*self.audio_data),
        )
        return bytes([*self.block_id.to_binary(file_info), *bytes(bin)])


class _BinaryFields(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("pack", ctypes.c_uint8 * 5),
        ("data", ctypes.c_uint8 * 72),
    ]


# Audio shuffling patterns


@dataclass(frozen=True, kw_only=True)
class _SamplePosition:
    # The DIF sequence number within the given audio block.  Remember that there are multiple
    # audio blocks available within a video frame, and each one is only 5 or 6 DIF
    # sequences/tracks in length.  Also known as the track number.
    dif_sequence_offset: int

    # The number of the audio DIF block within a sequence; also known as sync block number.
    dif_block: int

    # Sample-based offset into the audio data portion.  Multiply by 2 for 16-bit samples, or
    # 3 for dual-channel 12-bit samples, to obtain byte offset.
    data_offset: int


@dataclass(frozen=True, kw_only=True)
class _BlockPosition:
    # Same definitions as above.
    dif_sequence_offset: int
    dif_block: int


def _shuffle_audio_sample_numbers(
    video_frame_dif_sequence_count: int, max_sample_count: int
) -> list[_SamplePosition]:
    # Audio shuffling pattern defined in IEC 61834-2:1998 Section 6.7.
    # SMPTE 306M-2002 Section 7.3 Audio shuffling, has an identical subset of this shuffling pattern
    # for the formats that standard supports.
    #
    # The results are valid for both 1-channel 16-bit quantization, as well as 2-channel 12-bit
    # quantization, since results are given in sample offsets and not byte offsets.
    #
    # The return list is indexed by audio sample number within a single video frame.
    assert video_frame_dif_sequence_count == 10 or video_frame_dif_sequence_count == 12
    half_dif_sequence = int(video_frame_dif_sequence_count / 2)

    sample_positions = []
    for n in range(max_sample_count):
        sample_positions.append(
            _SamplePosition(
                dif_sequence_offset=(int(n / 3) + 2 * (n % 3)) % half_dif_sequence,
                dif_block=(
                    3 * (n % 3) + int((n % (9 * half_dif_sequence)) / (3 * half_dif_sequence))
                ),
                data_offset=int(n / (9 * half_dif_sequence)),
            )
        )
    return sample_positions


# Map a simple audio sample number to the exact position within the video frame.
#
# We only care about the maximum number of samples in the maximum sample rate.  Lower
# sample rates will simply ignore the rest of the array.
#
# The dictionary key is the total number of DIF sequences in a channel.
_audio_sample_positions: dict[int, list[_SamplePosition]] = {
    10: _shuffle_audio_sample_numbers(10, 1620),
    12: _shuffle_audio_sample_numbers(12, 1944),
}


def _reverse_shuffled_positions(
    sample_positions: list[_SamplePosition],
) -> dict[_BlockPosition, list[int]]:
    block_info: dict[_BlockPosition, list[int]] = defaultdict(list[int])
    for sample_number in range(len(sample_positions)):
        sample_position = sample_positions[sample_number]
        lst = block_info[
            _BlockPosition(
                dif_sequence_offset=sample_position.dif_sequence_offset,
                dif_block=sample_position.dif_block,
            )
        ]
        assert len(lst) == sample_position.data_offset
        lst.append(sample_number)
    return block_info


# Map a DIF block within the video frame to a list of audio sample numbers for that block
#
# The dictionary key is the total number of DIF sequences in a channel.
_sample_positions_to_numbers: dict[int, dict[_BlockPosition, list[int]]] = {
    video_frame_dif_sequence_count: _reverse_shuffled_positions(sample_positions)
    for video_frame_dif_sequence_count, sample_positions in _audio_sample_positions.items()
}
