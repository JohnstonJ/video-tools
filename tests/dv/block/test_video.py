from dataclasses import dataclass
from typing import cast

import pytest

import tests.dv.block.test_base as test_base
import video_tools.dv.block as block
from tests.dv.block.test_base import BlockBinaryTestCase
from tests.dv.util import NTSC_FILE


@dataclass(kw_only=True)
class VideoBlockBinaryTestCase(BlockBinaryTestCase):
    want_video_errors: bool


@pytest.mark.parametrize(
    "tc",
    [
        # ===== Real DIF blocks that I have captured from a Sony DCR-TRV460 =====
        VideoBlockBinaryTestCase(
            name="sony camcorder: no errors",
            # 32 kHz 12-bit 2-channel format
            input="91 47 6A "
            "05"
            "FAEEBFF25CB7F6FBF0EE09FB7EBD31EF7ED19FBAE27B3FC93FC6"
            "6B9125EEBFB16F67DBBFEB3DBF777F7F3BEEFFB29EEFF19F6760"
            "7F1BF6F6FEA081C34F4DBCE12E9706B99A4715AA56E10148",
            parsed=block.Video(
                block_id=block.BlockID(
                    type=block.BlockType.VIDEO,
                    sequence=0x1,
                    channel=0,
                    dif_sequence=4,
                    dif_block=106,
                ),
                status=0x0,
                quantization_number=0x5,
                dct_blocks=bytes(
                    bytes.fromhex(
                        "FAEEBFF25CB7F6FBF0EE09FB7EBD31EF7ED19FBAE27B3FC93FC6"
                        "6B9125EEBFB16F67DBBFEB3DBF777F7F3BEEFFB29EEFF19F6760"
                        "7F1BF6F6FEA081C34F4DBCE12E9706B99A4715AA56E10148"
                    )
                ),
            ),
            file_info=NTSC_FILE,
            want_video_errors=False,
        ),
        VideoBlockBinaryTestCase(
            name="sony camcorder: concealed error",
            # 32 kHz 12-bit 2-channel format
            input="9F 47 6B "
            "A5"
            "D12DD8888D6865E73B92AE650C00DD2EBF6A19FB4115F7DF2502"
            "5314CEA4432C9090A1C803D800000000D4152210035CCE2FD520"
            "62E30600022C4C0000000000000002B41CD6000000000000",
            parsed=block.Video(
                block_id=block.BlockID(
                    type=block.BlockType.VIDEO,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=4,
                    dif_block=107,
                ),
                status=0xA,
                quantization_number=0x5,
                dct_blocks=bytes(
                    bytes.fromhex(
                        "D12DD8888D6865E73B92AE650C00DD2EBF6A19FB4115F7DF2502"
                        "5314CEA4432C9090A1C803D800000000D4152210035CCE2FD520"
                        "62E30600022C4C0000000000000002B41CD6000000000000"
                    )
                ),
            ),
            file_info=NTSC_FILE,
            want_video_errors=True,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_video_block_binary(tc: VideoBlockBinaryTestCase) -> None:
    test_base.run_block_binary_test_case(tc)

    # Also check error detection
    assert cast(block.Video, tc.parsed).has_video_errors() == tc.want_video_errors
