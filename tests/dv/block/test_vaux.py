import pytest

import tests.dv.block.test_base as test_base
import video_tools.dv.block as block
import video_tools.dv.pack as pack
from tests.dv.block.test_base import BlockBinaryTestCase
from tests.dv.util import NTSC_FILE

TRAILER = "".join([" FF"] * 2)


@pytest.mark.parametrize(
    "tc",
    [
        # ===== Synthetic DIF blocks / contrived examples =====
        BlockBinaryTestCase(
            name="corrupted pack",
            input="5A 57 02 "
            "62 FFC1E10A "  # units position of "year" is 0xA: impossible!
            f"{"".join(["FF FFFFFFFF "]*14)}"
            f"{TRAILER}",
            output="5A 57 02 "
            "FF FFFFFFFF "  # corrupted pack will be cleared out
            f"{"".join(["FF FFFFFFFF "]*14)}"
            f"{TRAILER}",
            parsed=block.VAUX(
                block_id=block.BlockID(
                    type=block.Type.VAUX,
                    sequence=0xA,
                    channel=0,
                    dif_sequence=5,
                    dif_block=2,
                ),
                packs=[None, *[pack.NoInfo()] * 14],
                pack_types=[0x62, *[0xFF] * 14],
            ),
            file_info=NTSC_FILE,
        ),
        # ===== Real DIF blocks that I have captured from a Sony DCR-TRV460 =====
        BlockBinaryTestCase(
            name="sony camcorder: even DIF sequence number",
            # freshly recorded and flawless
            input="5A 27 02 "
            f"{"".join(["FF FFFFFFFF "]*9)}"
            "60 FFFF00FF "
            "61 0380FCFF "
            "62 FFC8E724 "
            "63 FFD8D5D9 "
            f"{"".join(["FF FFFFFFFF "]*2)}"
            f"{TRAILER}",
            parsed=block.VAUX(
                block_id=block.BlockID(
                    type=block.Type.VAUX,
                    sequence=0xA,
                    channel=0,
                    dif_sequence=2,
                    dif_block=2,
                ),
                packs=[
                    *[pack.NoInfo()] * 9,
                    pack.VAUXSource(
                        source_code=pack.SourceCode.CAMERA,
                        tv_channel=None,
                        tuner_category=None,
                        source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                        field_count=60,
                        bw_flag=pack.BlackAndWhiteFlag.COLOR,
                        color_frames_id_valid=False,
                        color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
                    ),
                    pack.VAUXSourceControl(
                        broadcast_system=0x0,
                        display_mode=0x0,
                        frame_field=pack.FrameField.BOTH,
                        first_second=1,
                        frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                        interlaced=True,
                        still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                        still_camera_picture=False,
                        copy_protection=pack.CopyProtection.NO_RESTRICTION,
                        source_situation=None,
                        input_source=pack.InputSource.ANALOG,
                        compression_count=pack.CompressionCount.CMP_1,
                        recording_start_point=False,
                        recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                        genre_category=0x7F,
                        reserved=0x1,
                    ),
                    pack.VAUXRecordingDate(
                        year=2024,
                        month=7,
                        day=8,
                        week=None,
                        time_zone_hours=None,
                        time_zone_30_minutes=None,
                        daylight_saving_time=None,
                        reserved=0x3,
                    ),
                    pack.VAUXRecordingTime(
                        hour=19,
                        minute=55,
                        second=58,
                        frame=None,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.SYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                    ),
                    *[pack.NoInfo()] * 2,
                ],
                pack_types=[*[0xFF] * 9, 0x60, 0x61, 0x62, 0x63, *[0xFF] * 2],
            ),
            file_info=NTSC_FILE,
        ),
        BlockBinaryTestCase(
            name="sony camcorder: odd DIF sequence number",
            # freshly recorded and flawless
            input="5A 37 00 "
            "60 FFFF00FF "
            "61 0380FCFF "
            "62 FFC8E724 "
            "63 FFD8D5D9 "
            f"{"".join(["FF FFFFFFFF "]*11)}"
            f"{TRAILER}",
            parsed=block.VAUX(
                block_id=block.BlockID(
                    type=block.Type.VAUX,
                    sequence=0xA,
                    channel=0,
                    dif_sequence=3,
                    dif_block=0,
                ),
                packs=[
                    pack.VAUXSource(
                        source_code=pack.SourceCode.CAMERA,
                        tv_channel=None,
                        tuner_category=None,
                        source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                        field_count=60,
                        bw_flag=pack.BlackAndWhiteFlag.COLOR,
                        color_frames_id_valid=False,
                        color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
                    ),
                    pack.VAUXSourceControl(
                        broadcast_system=0x0,
                        display_mode=0x0,
                        frame_field=pack.FrameField.BOTH,
                        first_second=1,
                        frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                        interlaced=True,
                        still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                        still_camera_picture=False,
                        copy_protection=pack.CopyProtection.NO_RESTRICTION,
                        source_situation=None,
                        input_source=pack.InputSource.ANALOG,
                        compression_count=pack.CompressionCount.CMP_1,
                        recording_start_point=False,
                        recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                        genre_category=0x7F,
                        reserved=0x1,
                    ),
                    pack.VAUXRecordingDate(
                        year=2024,
                        month=7,
                        day=8,
                        week=None,
                        time_zone_hours=None,
                        time_zone_30_minutes=None,
                        daylight_saving_time=None,
                        reserved=0x3,
                    ),
                    pack.VAUXRecordingTime(
                        hour=19,
                        minute=55,
                        second=58,
                        frame=None,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.SYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                    ),
                    *[pack.NoInfo()] * 11,
                ],
                pack_types=[0x60, 0x61, 0x62, 0x63, *[0xFF] * 11],
            ),
            file_info=NTSC_FILE,
        ),
        BlockBinaryTestCase(
            name="sony camcorder: total dropout",
            input=f"5A 37 00 {"".join(["FF FFFFFFFF "]*15)} {TRAILER}",
            parsed=block.VAUX(
                block_id=block.BlockID(
                    type=block.Type.VAUX,
                    sequence=0xA,
                    channel=0,
                    dif_sequence=3,
                    dif_block=0,
                ),
                packs=[*[pack.NoInfo()] * 15],
                pack_types=[*[0xFF] * 15],
            ),
            file_info=NTSC_FILE,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_vaux_block_binary(tc: BlockBinaryTestCase) -> None:
    test_base.run_block_binary_test_case(tc)


def test_vaux_block_validate_read() -> None:
    """Test validation failures when reading a VAUX block from binary.

    This tests only specific exceptions raised when reading from binary.  Most other validations
    are tested in test_vaux_block_validate_write.
    """

    failure = "Reserved bits in DIF VAUX block are unexpectedly in use."
    with pytest.raises(block.BlockError, match=failure):
        block.VAUX.parse_binary(
            bytes.fromhex(
                # trailing reserved byte is not FF
                f"5A 37 00 {"".join(["FF FFFFFFFF "]*15)} FF FE",
            ),
            NTSC_FILE,
        )
