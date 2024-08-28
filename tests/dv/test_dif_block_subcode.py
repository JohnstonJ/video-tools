from dataclasses import dataclass

import pytest

import video_tools.dv.dif_block as dif_block
import video_tools.dv.dif_block_header as dif_block_header
import video_tools.dv.dif_block_parser as block_parser
import video_tools.dv.dif_block_subcode as dif_block_subcode
import video_tools.dv.dif_pack as pack
import video_tools.dv.file_info as dv_file_info
from tests.dv.util import NTSC_FILE

TRAILER = "".join([" FF"] * 29)


@dataclass(kw_only=True)
class SubcodeBlockBinaryTestCase:
    name: str
    input: str
    parsed: dif_block.Block
    output: str | None = None
    file_info: dv_file_info.DVFileInfo


@pytest.mark.parametrize(
    "tc",
    [
        # ===== Synthetic DIF blocks / contrived examples =====
        SubcodeBlockBinaryTestCase(
            name="ID parts with various invalid bits",
            input="3F 57 01 "
            "74B6 FF 62 FFE3F200 "  # invalid AP3 bits
            "7067 FF 62 FFE3F200 "
            "7007 FF 62 FFE3F200 "  # miscounted SYB bits
            "74B9 FF 62 FFE3F200 "
            "F06A FF 62 FFE3F200 "  # FR bit is wrong
            "700B FF 62 FFE3F200 "  # invalid APT bits
            f"{TRAILER}",
            # output has the invalid ID parts reset to 0xFFFF
            output="3F 57 01 "
            "FFFF FF 62 FFE3F200 "
            "7067 FF 62 FFE3F200 "
            "FFFF FF 62 FFE3F200 "
            "74B9 FF 62 FFE3F200 "
            "FFFF FF 62 FFE3F200 "
            "FFFF FF 62 FFE3F200 "
            f"{TRAILER}",
            parsed=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=5,
                    dif_block=1,
                ),
                index=[False, None, False, None],
                skip=[False, None, False, None],
                picture=[False, None, False, None],
                application_id_track=None,  # dropout
                application_id_3=None,  # dropout
                absolute_track_number_0=[None, 0x4B >> 1],  # dropout
                absolute_track_number_1=[0x06, None],  # dropout
                absolute_track_number_2=[None, None],  # dropout
                blank_flag=[None, dif_block_subcode.BlankFlag.CONTINUOUS],  # dropout
                packs=[
                    pack.VAUXRecordingDate(
                        year=2000,
                        month=12,
                        day=23,
                        reserved=0x3,
                    ),
                ]
                * 6,
                pack_types=[0x62, 0x62, 0x62, 0x62, 0x62, 0x62],
            ),
            file_info=NTSC_FILE,
        ),
        SubcodeBlockBinaryTestCase(
            name="test tag bits and alternate app IDs",
            # freshly recorded and flawless
            input="3F 57 01 "
            "54B6 FF FF FFFFFFFF "  # AP3 is 5
            "6067 FF FF FFFFFFFF "  # PP cleared
            "5008 FF FF FFFFFFFF "  # Skip cleared
            "34B9 FF FF FFFFFFFF "  # Index cleared
            "706A FF FF FFFFFFFF "
            "300B FF FF FFFFFFFF "  # APT is 3
            f"{TRAILER}",
            parsed=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=5,
                    dif_block=1,
                ),
                index=[False, False, True, False],
                skip=[False, True, False, False],
                picture=[True, False, False, False],
                application_id_track=dif_block_header.ApplicationIDTrack.RESERVED_3,
                application_id_3=dif_block_header.ApplicationID3.RESERVED_5,
                absolute_track_number_0=[0x4B >> 1] * 2,
                absolute_track_number_1=[0x06] * 2,
                absolute_track_number_2=[0x00] * 2,
                blank_flag=[dif_block_subcode.BlankFlag.CONTINUOUS] * 2,
                packs=[pack.NoInfo()] * 6,
                pack_types=[0xFF] * 6,
            ),
            file_info=NTSC_FILE,
        ),
        SubcodeBlockBinaryTestCase(
            name="corrupted pack",
            input="3F 57 01 "
            "04B6 FF 13 E08280CA "  # units position of "hours" is 0xA: impossible!
            "7067 FF FF FFFFFFFF "
            "7008 FF FF FFFFFFFF "
            "74B9 FF FF FFFFFFFF "
            "706A FF FF FFFFFFFF "
            "000B FF FF FFFFFFFF "
            f"{TRAILER}",
            output="3F 57 01 "
            "04B6 FF FF FFFFFFFF "  # corrupted pack will be cleared out
            "7067 FF FF FFFFFFFF "
            "7008 FF FF FFFFFFFF "
            "74B9 FF FF FFFFFFFF "
            "706A FF FF FFFFFFFF "
            "000B FF FF FFFFFFFF "
            f"{TRAILER}",
            parsed=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=5,
                    dif_block=1,
                ),
                index=[False] * 4,
                skip=[False] * 4,
                picture=[False] * 4,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
                absolute_track_number_0=[0x4B >> 1] * 2,
                absolute_track_number_1=[0x06] * 2,
                absolute_track_number_2=[0x00] * 2,
                blank_flag=[dif_block_subcode.BlankFlag.CONTINUOUS] * 2,
                packs=[None, *[pack.NoInfo()] * 5],
                pack_types=[0x13, *[0xFF] * 5],
            ),
            file_info=NTSC_FILE,
        ),
        # ===== Real DIF blocks that I have captured from a Sony DCR-TRV460 =====
        SubcodeBlockBinaryTestCase(
            name="sony camcorder: no errors, back half of frame",
            # freshly recorded and flawless
            input="3F 57 01 "
            "04B6 FF 13 E08280C0 "
            "7067 FF 62 FFC8E724 "
            "7008 FF 63 FFD8D5D9 "
            "74B9 FF 13 E08280C0 "
            "706A FF 62 FFC8E724 "
            "000B FF 63 FFD8D5D9 "
            f"{TRAILER}",
            parsed=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=5,
                    dif_block=1,
                ),
                index=[False] * 4,
                skip=[False] * 4,
                picture=[False] * 4,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
                absolute_track_number_0=[0x4B >> 1] * 2,
                absolute_track_number_1=[0x06] * 2,
                absolute_track_number_2=[0x00] * 2,
                blank_flag=[dif_block_subcode.BlankFlag.CONTINUOUS] * 2,
                packs=[
                    pack.TitleTimecode(
                        hour=0,
                        minute=0,
                        second=2,
                        frame=20,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.SYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                        blank_flag=pack.BlankFlag.CONTINUOUS,
                    ),
                    pack.VAUXRecordingDate(
                        year=2024,
                        month=7,
                        day=8,
                        reserved=0x3,
                    ),
                    pack.VAUXRecordingTime(
                        hour=19,
                        minute=55,
                        second=58,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.SYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                    ),
                ]
                * 2,
                pack_types=[0x13, 0x62, 0x63, 0x13, 0x62, 0x63],
            ),
            file_info=NTSC_FILE,
        ),
        SubcodeBlockBinaryTestCase(
            name="sony camcorder: no errors, front half of frame",
            # freshly recorded and flawless
            input="3F 47 00 "
            "8490 FF 13 E08280C0 "
            "F061 FF 13 E08280C0 "
            "F002 FF 13 E08280C0 "
            "F493 FF 13 E08280C0 "
            "F064 FF 13 E08280C0 "
            "F005 FF 13 E08280C0 "
            f"{TRAILER}",
            parsed=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=4,
                    dif_block=0,
                ),
                index=[False] * 5,
                skip=[False] * 5,
                picture=[False] * 5,
                application_id_track=None,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
                absolute_track_number_0=[0x49 >> 1] * 2,
                absolute_track_number_1=[0x06] * 2,
                absolute_track_number_2=[0x00] * 2,
                blank_flag=[dif_block_subcode.BlankFlag.CONTINUOUS] * 2,
                packs=[
                    pack.TitleTimecode(
                        hour=0,
                        minute=0,
                        second=2,
                        frame=20,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.SYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                        blank_flag=pack.BlankFlag.CONTINUOUS,
                    )
                ]
                * 6,
                pack_types=[0x13, 0x13, 0x13, 0x13, 0x13, 0x13],
            ),
            file_info=NTSC_FILE,
        ),
        SubcodeBlockBinaryTestCase(
            name="sony camcorder: lots of dropouts (1)",
            # from an ancient tape with lots of subcode read errors
            # also as a side note: this also helps us test absolute track numbers
            # with BF cleared and upper bits also in use
            input="3F 87 01 "
            "0D06 FF FF FFFFFFFF "
            "7B07 FF 62 FFE3F200 "
            "7168 FF 63 FF91D7D5 "
            "7D09 FF 13 58C9A0C0 "
            "7B0A FF 62 FFE3F200 "
            "FFFF FF FF FFFFFFFF "
            f"{TRAILER}",
            parsed=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=8,
                    dif_block=1,
                ),
                index=[False] * 4,
                skip=[False] * 4,
                picture=[False] * 4,
                application_id_track=None,  # dropout
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
                absolute_track_number_0=[0xD0 >> 1] * 2,
                absolute_track_number_1=[0xB0] * 2,
                absolute_track_number_2=[0x16, None],  # dropout
                blank_flag=[dif_block_subcode.BlankFlag.DISCONTINUOUS] * 2,
                packs=[
                    pack.NoInfo(),
                    pack.VAUXRecordingDate(
                        year=2000,
                        month=12,
                        day=23,
                        reserved=0x3,
                    ),
                    pack.VAUXRecordingTime(
                        hour=15,
                        minute=57,
                        second=11,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.SYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                    ),
                    pack.TitleTimecode(
                        hour=0,
                        minute=20,
                        second=49,
                        frame=18,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.UNSYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                        blank_flag=pack.BlankFlag.DISCONTINUOUS,
                    ),
                    pack.VAUXRecordingDate(
                        year=2000,
                        month=12,
                        day=23,
                        reserved=0x3,
                    ),
                    pack.NoInfo(),
                ],
                pack_types=[0xFF, 0x62, 0x63, 0x13, 0x62, 0xFF],
            ),
            file_info=NTSC_FILE,
        ),
        SubcodeBlockBinaryTestCase(
            name="sony camcorder: lots of dropouts (2)",
            # from an ancient tape with lots of subcode read errors
            input="3F 97 00 "
            "0D20 FF 13 58C9A0C0 "
            "7B01 FF 62 FFE3F200 "
            "7162 FF 63 FF91D7D5 "
            "7D23 FF 13 58C9A0C0 "
            "7B04 FF 62 FFE3F200 "
            # This next sync block ID part is interesting because the block number is valid,
            # but clearly the rest of the block (including the front half bit and app ID) is not.
            "FFF5 FF FF FFFFFFFF "
            f"{TRAILER}",
            # Output is identical to input, except the SYB bits were reset in the 6th sync block
            output="3F 97 00 "
            "0D20 FF 13 58C9A0C0 "
            "7B01 FF 62 FFE3F200 "
            "7162 FF 63 FF91D7D5 "
            "7D23 FF 13 58C9A0C0 "
            "7B04 FF 62 FFE3F200 "
            "FFFF FF FF FFFFFFFF "
            f"{TRAILER}",
            parsed=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=9,
                    dif_block=0,
                ),
                index=[*[False] * 4, None],  # dropout
                skip=[*[False] * 4, None],  # dropout
                picture=[*[False] * 4, None],  # dropout
                application_id_track=None,  # dropout
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
                absolute_track_number_0=[0xD2 >> 1] * 2,
                absolute_track_number_1=[0xB0] * 2,
                absolute_track_number_2=[0x16, None],  # dropout
                blank_flag=[dif_block_subcode.BlankFlag.DISCONTINUOUS] * 2,
                packs=[
                    pack.TitleTimecode(
                        hour=0,
                        minute=20,
                        second=49,
                        frame=18,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.UNSYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                        blank_flag=pack.BlankFlag.DISCONTINUOUS,
                    ),
                    pack.VAUXRecordingDate(
                        year=2000,
                        month=12,
                        day=23,
                        reserved=0x3,
                    ),
                    pack.VAUXRecordingTime(
                        hour=15,
                        minute=57,
                        second=11,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.SYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                    ),
                    pack.TitleTimecode(
                        hour=0,
                        minute=20,
                        second=49,
                        frame=18,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.UNSYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.ODD,
                        binary_group_flags=0x7,
                        blank_flag=pack.BlankFlag.DISCONTINUOUS,
                    ),
                    pack.VAUXRecordingDate(
                        year=2000,
                        month=12,
                        day=23,
                        reserved=0x3,
                    ),
                    pack.NoInfo(),
                ],
                pack_types=[0x13, 0x62, 0x63, 0x13, 0x62, 0xFF],
            ),
            file_info=NTSC_FILE,
        ),
        # DVCPRO50 color bars from https://archive.org/details/SMPTEColorBarsBadTracking
        SubcodeBlockBinaryTestCase(
            name="DVCPRO50 color bars",
            # from an ancient tape with lots of subcode read errors
            input="3F 2F 00 "
            "8000 FF 13 40000000"
            "F001 FF 14 00000000"
            "F002 FF 13 40000000"
            "F003 FF 13 40000000"
            "F004 FF 14 00000000"
            "F005 FF 13 40000000"
            f"{TRAILER}",
            parsed=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=1,
                    dif_sequence=2,
                    dif_block=0,
                ),
                index=[False] * 5,
                skip=[False] * 5,
                picture=[False] * 5,
                application_id_track=None,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
                absolute_track_number_0=[0x00 >> 1] * 2,
                absolute_track_number_1=[0x00] * 2,
                absolute_track_number_2=[0x00] * 2,
                blank_flag=[dif_block_subcode.BlankFlag.DISCONTINUOUS] * 2,
                packs=[
                    pack.TitleTimecode(
                        hour=0,
                        minute=0,
                        second=0,
                        frame=0,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.UNSYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.EVEN,
                        binary_group_flags=0x0,
                        blank_flag=pack.BlankFlag.DISCONTINUOUS,
                    ),
                    pack.TitleBinaryGroup(value=bytes([0x00] * 4)),
                    pack.TitleTimecode(
                        hour=0,
                        minute=0,
                        second=0,
                        frame=0,
                        drop_frame=True,
                        color_frame=pack.ColorFrame.UNSYNCHRONIZED,
                        polarity_correction=pack.PolarityCorrection.EVEN,
                        binary_group_flags=0x0,
                        blank_flag=pack.BlankFlag.DISCONTINUOUS,
                    ),
                ]
                * 2,
                pack_types=[0x13, 0x14, 0x13] * 2,
            ),
            file_info=NTSC_FILE,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_subcode_block_binary(tc: SubcodeBlockBinaryTestCase) -> None:
    parsed = block_parser.parse_binary(bytes.fromhex(tc.input), tc.file_info)
    assert parsed == tc.parsed
    updated = parsed.to_binary(tc.file_info)
    assert updated == bytes.fromhex(tc.output if tc.output is not None else tc.input)


@dataclass
class SubcodeBlockValidateTestCase:
    name: str
    input: dif_block_subcode.Subcode
    failure: str
    file_info: dv_file_info.DVFileInfo


@pytest.mark.parametrize(
    "tc",
    [
        SubcodeBlockValidateTestCase(
            name="wrong DIF block number",
            input=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=2,
                ),
                index=[None] * 5,
                skip=[None] * 5,
                picture=[None] * 5,
                application_id_track=None,
                application_id_3=None,
                absolute_track_number_2=[None] * 2,
                absolute_track_number_1=[None] * 2,
                absolute_track_number_0=[None] * 2,
                blank_flag=[None] * 2,
                packs=[None] * 6,
                pack_types=[0xFF] * 6,
            ),
            failure="Unexpected number of DIF blocks in DIF sequence; expected 2.",
            file_info=NTSC_FILE,
        ),
        SubcodeBlockValidateTestCase(
            name="uneven ID part presence (skip present)",
            input=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                index=[None] * 5,
                skip=[True, *[None] * 4],  # skip is present
                picture=[None] * 5,
                application_id_track=None,
                application_id_3=None,
                absolute_track_number_2=[None] * 2,
                absolute_track_number_1=[None] * 2,
                absolute_track_number_0=[None] * 2,
                blank_flag=[None] * 2,
                packs=[None] * 6,
                pack_types=[0xFF] * 6,
            ),
            failure="All parts of sync block 1 must be all present or absent.",
            file_info=NTSC_FILE,
        ),
        SubcodeBlockValidateTestCase(
            name="uneven ID part presence (picture present)",
            input=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                index=[None] * 5,
                skip=[None] * 5,
                picture=[True, *[None] * 4],  # picture is present
                application_id_track=None,
                application_id_3=None,
                absolute_track_number_2=[None] * 2,
                absolute_track_number_1=[None] * 2,
                absolute_track_number_0=[None] * 2,
                blank_flag=[None] * 2,
                packs=[None] * 6,
                pack_types=[0xFF] * 6,
            ),
            failure="All parts of sync block 1 must be all present or absent.",
            file_info=NTSC_FILE,
        ),
        SubcodeBlockValidateTestCase(
            name="uneven ID part presence (ATN0 present)",
            input=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                index=[None] * 5,
                skip=[None] * 5,
                picture=[None] * 5,
                application_id_track=None,
                application_id_3=None,
                absolute_track_number_2=[None] * 2,
                absolute_track_number_1=[None] * 2,
                absolute_track_number_0=[0x00, None],  # ATN lower byte is present
                blank_flag=[None] * 2,
                packs=[None] * 6,
                pack_types=[0xFF] * 6,
            ),
            failure="All parts of sync block 0 must be all present or absent.",
            file_info=NTSC_FILE,
        ),
        SubcodeBlockValidateTestCase(
            name="uneven ID part presence (BF present)",
            input=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                index=[None] * 5,
                skip=[None] * 5,
                picture=[None] * 5,
                application_id_track=None,
                application_id_3=None,
                absolute_track_number_2=[None] * 2,
                absolute_track_number_1=[None] * 2,
                absolute_track_number_0=[None] * 2,
                blank_flag=[dif_block_subcode.BlankFlag.CONTINUOUS, None],  # blank flag is present
                packs=[None] * 6,
                pack_types=[0xFF] * 6,
            ),
            failure="All parts of sync block 0 must be all present or absent.",
            file_info=NTSC_FILE,
        ),
        SubcodeBlockValidateTestCase(
            name="uneven ID part presence (ATN1 present)",
            input=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                index=[None] * 5,
                skip=[None] * 5,
                picture=[None] * 5,
                application_id_track=None,
                application_id_3=None,
                absolute_track_number_2=[None] * 2,
                absolute_track_number_1=[0x00, None],  # ATN middle byte is present
                absolute_track_number_0=[None] * 2,
                blank_flag=[None] * 2,
                packs=[None] * 6,
                pack_types=[0xFF] * 6,
            ),
            failure="All parts of sync block 1 must be all present or absent.",
            file_info=NTSC_FILE,
        ),
        SubcodeBlockValidateTestCase(
            name="uneven ID part presence (ATN2 present)",
            input=dif_block_subcode.Subcode(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.SUBCODE,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                index=[None] * 5,
                skip=[None] * 5,
                picture=[None] * 5,
                application_id_track=None,
                application_id_3=None,
                absolute_track_number_2=[0x00, None],  # ATN upper byte is present
                absolute_track_number_1=[None] * 2,
                absolute_track_number_0=[None] * 2,
                blank_flag=[None] * 2,
                packs=[None] * 6,
                pack_types=[0xFF] * 6,
            ),
            failure="All parts of sync block 2 must be all present or absent.",
            file_info=NTSC_FILE,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_subcode_block_validate_write(tc: SubcodeBlockValidateTestCase) -> None:
    """Test validation failures when writing a subcode block to binary."""
    with pytest.raises(dif_block.BlockError, match=tc.failure):
        tc.input.to_binary(tc.file_info)


def test_subcode_block_validate_read() -> None:
    """Test validation failures when reading a subcode block from binary.

    This tests only specific exceptions raised when reading from binary.  Most other validations
    are tested in test_subcode_block_validate_write.
    """
    failure = "Sync block parity byte is not 0xFF for sync block 8."
    with pytest.raises(dif_block.BlockError, match=failure):
        dif_block_subcode.Subcode.parse_binary(
            bytes.fromhex(
                "3F 57 01 "
                "04B6 FF 13 E08280C0 "
                "7067 FF 62 FFC8E724 "
                "7008 00 63 FFD8D5D9 "  # parity bit is 0x00
                "74B9 FF 13 E08280C0 "
                "706A FF 62 FFC8E724 "
                "000B FF 63 FFD8D5D9 "
                f"{TRAILER}"
            ),
            NTSC_FILE,
        )

    failure = "Reserved bits in DIF header block are unexpectedly in use."
    with pytest.raises(dif_block.BlockError, match=failure):
        dif_block_subcode.Subcode.parse_binary(
            bytes.fromhex(
                "3F 57 01 "
                "04B6 FF 13 E08280C0 "
                "7067 FF 62 FFC8E724 "
                "7008 FF 63 FFD8D5D9 "
                "74B9 FF 13 E08280C0 "
                "706A FF 62 FFC8E724 "
                "000B FF 63 FFD8D5D9 "
                f"FE {"".join([" FF"] * 28)}"  # trailing reserved byte is not FF
            ),
            NTSC_FILE,
        )
