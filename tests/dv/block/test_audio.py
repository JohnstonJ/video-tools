from dataclasses import dataclass

import pytest

import tests.dv.block.test_base as test_base
import video_tools.dv.block as block
import video_tools.dv.file.info as dv_file_info
import video_tools.dv.pack as pack
from tests.dv.block.test_base import BlockBinaryTestCase
from tests.dv.util import NTSC_FILE
from video_tools.dv.block.audio import (
    _audio_sample_positions,
    _BlockPosition,
    _sample_positions_to_numbers,
    _SamplePosition,
)


@pytest.mark.parametrize(
    "tc",
    [
        # ===== Synthetic DIF blocks / contrived examples =====
        BlockBinaryTestCase(
            name="corrupted pack",
            input="7A 67 05 "
            "52 FFC1E10A "  # units position of "year" is 0xA: impossible!
            f"{"".join(["12 34 56 "]*24)}",
            output="7A 67 05 "
            "FF FFFFFFFF "  # corrupted pack will be cleared out
            f"{"".join(["12 34 56 "]*24)}",
            parsed=block.Audio(
                block_id=block.BlockID(
                    type=block.BlockType.AUDIO,
                    sequence=0xA,
                    channel=0,
                    dif_sequence=6,
                    dif_block=5,
                ),
                pack_data=None,
                pack_type=0x52,
                audio_data=bytes([0x12, 0x34, 0x56] * 24),
            ),
            file_info=NTSC_FILE,
        ),
        # ===== Real DIF blocks that I have captured from a Sony DCR-TRV460 =====
        BlockBinaryTestCase(
            name="sony camcorder: with pack",
            # 32 kHz 12-bit 2-channel format
            input="78 27 05 "
            "52 FFC8E724 "
            "BB10AA5A58812F29ACA2A61A13F26E4E53CD5445EDA6AA81A0A57E5B55E83B352063616F"
            "9A993C3F3B0D5A5389B2B468A6A904494816D639E1492136ACB070B7C0834B3F1FF202C6",
            parsed=block.Audio(
                block_id=block.BlockID(
                    type=block.BlockType.AUDIO,
                    sequence=0x8,
                    channel=0,
                    dif_sequence=2,
                    dif_block=5,
                ),
                pack_data=pack.AAUXRecordingDate(year=2024, month=7, day=8, reserved=0x3),
                pack_type=0x52,
                audio_data=bytes(
                    bytes.fromhex(
                        "BB10AA5A58812F29ACA2A61A13F26E4E53CD5445EDA6AA81A0A57E5B55E83B352063616F"
                        "9A993C3F3B0D5A5389B2B468A6A904494816D639E1492136ACB070B7C0834B3F1FF202C6"
                    )
                ),
            ),
            file_info=NTSC_FILE,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_audio_block_binary(tc: BlockBinaryTestCase) -> None:
    test_base.run_block_binary_test_case(tc)


@dataclass
class ShufflePatternTestCase:
    dif_seq_count: int  # within a single channel
    sample_number: int
    pos_seq: int
    pos_block: int
    pos_offset: int


@pytest.mark.parametrize(
    "tc",
    [
        # Values taken from IEC 61834-2:1998 Figure 19 - Audio shuffling pattern for 525-60 system:
        # 48k mode/44,1k mode/32k mode
        ShufflePatternTestCase(
            dif_seq_count=10,
            sample_number=76,
            pos_seq=2,
            pos_block=5,
            pos_offset=1,
        ),
        ShufflePatternTestCase(
            dif_seq_count=10,
            sample_number=1532,
            pos_seq=4,
            pos_block=6,
            pos_offset=34,
        ),
        ShufflePatternTestCase(
            dif_seq_count=10,
            sample_number=1598,
            pos_seq=1,
            pos_block=7,
            pos_offset=35,
        ),
        # Values taken from IEC 61834-2:1998 Figure 20 - Audio shuffling pattern for 625-50 system:
        # 48k mode/44,1k mode/32k mode
        ShufflePatternTestCase(
            dif_seq_count=12,
            sample_number=147,
            pos_seq=1,
            pos_block=2,
            pos_offset=2,
        ),
        ShufflePatternTestCase(
            dif_seq_count=12,
            sample_number=1881,
            pos_seq=3,
            pos_block=2,
            pos_offset=34,
        ),
        ShufflePatternTestCase(
            dif_seq_count=12,
            sample_number=1913,
            pos_seq=5,
            pos_block=7,
            pos_offset=35,
        ),
        # Values taken from IEC 61834-2:1998 Figure 21 - Audio shuffling pattern for 525-60 system:
        # 32k-2ch mode
        ShufflePatternTestCase(
            dif_seq_count=10,
            sample_number=56,
            pos_seq=2,
            pos_block=6,
            pos_offset=1,
        ),
        ShufflePatternTestCase(
            dif_seq_count=10,
            sample_number=1023,
            pos_seq=1,
            pos_block=2,
            pos_offset=22,
        ),
        ShufflePatternTestCase(
            dif_seq_count=10,
            sample_number=1037,
            pos_seq=4,
            pos_block=6,
            pos_offset=23,
        ),
        # Values taken from IEC 61834-2:1998 Figure 22 - Audio shuffling pattern for 625-50 system:
        # 32k-2ch mode
        ShufflePatternTestCase(
            dif_seq_count=12,
            sample_number=124,
            pos_seq=1,
            pos_block=3,
            pos_offset=2,
        ),
        ShufflePatternTestCase(
            dif_seq_count=12,
            sample_number=1233,
            pos_seq=3,
            pos_block=2,
            pos_offset=22,
        ),
        ShufflePatternTestCase(
            dif_seq_count=12,
            sample_number=1265,
            pos_seq=5,
            pos_block=7,
            pos_offset=23,
        ),
    ],
    ids=lambda tc: f"{tc.dif_seq_count} {tc.sample_number}",
)
def test_audio_shuffle_pattern(tc: ShufflePatternTestCase) -> None:
    assert _audio_sample_positions[tc.dif_seq_count][tc.sample_number] == _SamplePosition(
        dif_sequence_offset=tc.pos_seq,
        dif_block=tc.pos_block,
        data_offset=tc.pos_offset,
    )

    assert (
        (
            _sample_positions_to_numbers[tc.dif_seq_count][
                _BlockPosition(dif_sequence_offset=tc.pos_seq, dif_block=tc.pos_block)
            ][tc.pos_offset]
        )
        == tc.sample_number
    )


@dataclass
class AudioErrorTestCase:
    name: str
    dif_sequence: int
    dif_block: int
    audio_data: str
    file_info: dv_file_info.Info
    sample_count: int
    quantization: pack.AudioQuantization
    want_errors: bool


@pytest.mark.parametrize(
    "tc",
    [
        # Real world data from my Sony DCR-TRV460 camcorder: sometimes modified, sometimes tweaked,
        # as noted below.  Sample index numbers in the comments come from the shuffle table.
        AudioErrorTestCase(
            name="sony camcorder, good block",
            dif_sequence=2,
            dif_block=1,
            # unmodified: last sample index is #1053
            audio_data=""
            "5D5B9D564DB6A2A6609FA5D24648F064655AC5BDC79A9FCB2E20605B56FAB5BB0B595214"
            "A7AE985450BF421560A8AD59C2C4774C475556591BB3B022A5A8AD524B904838A0AEB38D",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=False,
        ),
        AudioErrorTestCase(
            name="sony camcorder, bad block",
            dif_sequence=2,
            dif_block=1,
            # Tweaked: take the previous example, but mark the last sample as an error sample.
            audio_data=""
            "5D5B9D564DB6A2A6609FA5D24648F064655AC5BDC79A9FCB2E20605B56FAB5BB0B595214"
            "A7AE985450BF421560A8AD59C2C4774C475556591BB3B022A5A8AD524B904838A0808000",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=True,
        ),
        AudioErrorTestCase(
            name="sony camcorder, good block with empty sample at the end",
            dif_sequence=2,
            dif_block=2,
            # unmodified: last sample index is (zero-based) #1068, higher than the sample_count,
            # and thus left as zero by the camera.
            audio_data=""
            "A7B893505174514C83ABAD4331F784CA18A2584B39C7C1109B9E6A504BAB494336656556"
            "9A9989C7CE355B5405C2CB44A1A63C524F58AEC96852424CD2CC88A8B22C3A344C000000",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=False,
        ),
        AudioErrorTestCase(
            name="sony camcorder, good block with bad but unused sample at the end",
            dif_sequence=2,
            dif_block=2,
            # Tweaked: take the previous example, but mark it as an error sample.  The block is
            # still not marked as error, because it's not a sample we care about to begin with.
            audio_data=""
            "A7B893505174514C83ABAD4331F784CA18A2584B39C7C1109B9E6A504BAB494336656556"
            "9A9989C7CE355B5405C2CB44A1A63C524F58AEC96852424CD2CC88A8B22C3A344C808000",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=False,
        ),
        # The next four test cases are identical to the previous ones with the same names that
        # were in the first audio block (remove parenthesis from the name).  They effectively
        # test that shuffling still works correctly in the second audio block/channel in the
        # DIF sequence/track.
        AudioErrorTestCase(
            name="sony camcorder, good block (second audio block)",
            dif_sequence=2 + 5,
            dif_block=1,
            # unmodified: last sample index is #1053
            audio_data=""
            "5D5B9D564DB6A2A6609FA5D24648F064655AC5BDC79A9FCB2E20605B56FAB5BB0B595214"
            "A7AE985450BF421560A8AD59C2C4774C475556591BB3B022A5A8AD524B904838A0AEB38D",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=False,
        ),
        AudioErrorTestCase(
            name="sony camcorder, bad block (second audio block)",
            dif_sequence=2 + 5,
            dif_block=1,
            # Tweaked: take the previous example, but mark the last sample as an error sample.
            audio_data=""
            "5D5B9D564DB6A2A6609FA5D24648F064655AC5BDC79A9FCB2E20605B56FAB5BB0B595214"
            "A7AE985450BF421560A8AD59C2C4774C475556591BB3B022A5A8AD524B904838A0808000",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=True,
        ),
        AudioErrorTestCase(
            name="sony camcorder, good block with empty sample at the end (second audio block)",
            dif_sequence=2 + 5,
            dif_block=2,
            # unmodified: last sample index is (zero-based) #1068, higher than the sample_count,
            # and thus left as zero by the camera.
            audio_data=""
            "A7B893505174514C83ABAD4331F784CA18A2584B39C7C1109B9E6A504BAB494336656556"
            "9A9989C7CE355B5405C2CB44A1A63C524F58AEC96852424CD2CC88A8B22C3A344C000000",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=False,
        ),
        AudioErrorTestCase(
            name="sony camcorder, good block with bad but unused sample "
            "at the end (second audio block)",
            dif_sequence=2 + 5,
            dif_block=2,
            # Tweaked: take the previous example, but mark it as an error sample.  The block is
            # still not marked as error, because it's not a sample we care about to begin with.
            audio_data=""
            "A7B893505174514C83ABAD4331F784CA18A2584B39C7C1109B9E6A504BAB494336656556"
            "9A9989C7CE355B5405C2CB44A1A63C524F58AEC96852424CD2CC88A8B22C3A344C808000",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=False,
        ),
        # More tweaked cases from my Sony camcorder
        AudioErrorTestCase(
            name="sony camcorder, left half invalid",
            dif_sequence=2,
            dif_block=1,
            # tweaked: last sample index is #1053, only one half of the sample invalid
            audio_data=""
            "5D5B9D564DB6A2A6609FA5D24648F064655AC5BDC79A9FCB2E20605B56FAB5BB0B595214"
            "A7AE985450BF421560A8AD59C2C4774C475556591BB3B022A5A8AD524B904838A080B30D",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=True,
        ),
        AudioErrorTestCase(
            name="sony camcorder, right half invalid",
            dif_sequence=2,
            dif_block=1,
            # tweaked: last sample index is #1053, only one half of the sample invalid
            audio_data=""
            "5D5B9D564DB6A2A6609FA5D24648F064655AC5BDC79A9FCB2E20605B56FAB5BB0B595214"
            "A7AE985450BF421560A8AD59C2C4774C475556591BB3B022A5A8AD524B904838A0AE8080",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=True,
        ),
        # More unmodified cases from my Sony camcorder
        AudioErrorTestCase(
            name="sony camcorder, full dropout",
            dif_sequence=2,
            dif_block=1,
            # unmodified
            audio_data=""
            "808000808000808000808000808000808000808000808000808000808000808000808000"
            "808000808000808000808000808000808000808000808000808000808000808000808000",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=True,
        ),
        AudioErrorTestCase(
            name="sony camcorder, empty channel",
            dif_sequence=2,
            dif_block=1,
            # unmodified
            audio_data=""
            "000000000000000000000000000000000000000000000000000000000000000000000000"
            "000000000000000000000000000000000000000000000000000000000000000000000000",
            file_info=NTSC_FILE,
            sample_count=1068,
            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
            want_errors=False,
        ),
        # Everything on my camcorder was NTSC 12-bit 2-channel.  Some alternative synthetic blocks:
        AudioErrorTestCase(
            name="synthetic 16-bit, no errors",
            dif_sequence=2,
            dif_block=1,
            # last sample is #1596 and thus excluded
            audio_data=""
            "000000000000000000000000000000000000000000000000000000000000000000000000"
            "000000000000000000000000000000000000000000000000000000000000000000000000",
            file_info=NTSC_FILE,
            sample_count=1596,
            quantization=pack.AudioQuantization.LINEAR_16_BIT,
            want_errors=False,
        ),
        AudioErrorTestCase(
            name="synthetic 16-bit, with error",
            dif_sequence=2,
            dif_block=1,
            # last sample is #1596 and thus excluded. but we have an error on the one before
            audio_data=""
            "000000000000000000000000000000000000000000000000000000000000000000000000"
            "000000000000000000000000000000000000000000000000000000000000000080000000",
            file_info=NTSC_FILE,
            sample_count=1596,
            quantization=pack.AudioQuantization.LINEAR_16_BIT,
            want_errors=True,
        ),
        AudioErrorTestCase(
            name="synthetic 16-bit, with error in unused sample",
            dif_sequence=2,
            dif_block=1,
            # last sample is #1596 and thus excluded. it won't cause an error
            audio_data=""
            "000000000000000000000000000000000000000000000000000000000000000000000000"
            "000000000000000000000000000000000000000000000000000000000000000000008000",
            file_info=NTSC_FILE,
            sample_count=1596,
            quantization=pack.AudioQuantization.LINEAR_16_BIT,
            want_errors=False,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_audio_error_detection(tc: AudioErrorTestCase) -> None:
    blk = block.Audio(
        block_id=block.BlockID(
            type=block.BlockType.AUDIO,
            sequence=0x0,
            channel=0,
            dif_sequence=tc.dif_sequence,
            dif_block=tc.dif_block,
        ),
        pack_data=None,
        pack_type=0xFF,
        audio_data=bytes.fromhex(tc.audio_data),
    )
    assert tc.want_errors == blk.has_audio_errors(tc.file_info, tc.sample_count, tc.quantization)
