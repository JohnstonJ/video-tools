from dataclasses import dataclass

import pytest

import video_tools.dv.dif_block as dif_block
import video_tools.dv.dif_block_header as dif_block_header
import video_tools.dv.dif_block_parser as block_parser
import video_tools.dv.file_info as dv_file_info
from tests.dv.util import NTSC_FILE, PAL_FILE

TRAILER = "".join([" FF"] * 72)


@dataclass
class HeaderBlockBinaryTestCase:
    name: str
    input: str
    parsed: dif_block.Block
    file_info: dv_file_info.DVFileInfo


@pytest.mark.parametrize(
    "tc",
    [
        # pedantic DIF blocks to exercise code branches
        HeaderBlockBinaryTestCase(
            name="variety of values",
            input=f"1F 07 00  BF 2A 7B 7C 7D {TRAILER}",
            parsed=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=12,
                track_pitch=dif_block_header.TrackPitch.D7_STANDARD_FORMAT,
                pilot_frame=0,
                application_id_track=dif_block_header.ApplicationIDTrack.RESERVED_2,
                application_id_1=dif_block_header.ApplicationID1.RESERVED_3,
                application_id_2=dif_block_header.ApplicationID2.RESERVED_4,
                application_id_3=dif_block_header.ApplicationID3.RESERVED_5,
            ),
            file_info=PAL_FILE,
        ),
        HeaderBlockBinaryTestCase(
            name="missing stuff",
            input=f"1F 07 00  3F FF 7F 7F 7F {TRAILER}",
            parsed=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=10,
                track_pitch=None,
                pilot_frame=None,
                application_id_track=None,
                application_id_1=None,
                application_id_2=None,
                application_id_3=None,
            ),
            file_info=NTSC_FILE,
        ),
        # real DIF blocks that I have captured from a Sony DCR-TRV460
        HeaderBlockBinaryTestCase(
            name="basic test: standard play, NTSC, consumer format, first header, pilot 1",
            input=f"1F 07 00  3F 78 78 78 78 {TRAILER}",
            parsed=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=10,
                track_pitch=dif_block_header.TrackPitch.STANDARD_PLAY,
                pilot_frame=1,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_1=dif_block_header.ApplicationID1.CONSUMER_DIGITAL_VCR,
                application_id_2=dif_block_header.ApplicationID2.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
            ),
            file_info=NTSC_FILE,
        ),
        HeaderBlockBinaryTestCase(
            name="basic test: standard play, NTSC, consumer format, first header, pilot 0",
            input=f"1F 07 00  3F 68 78 78 78 {TRAILER}",
            parsed=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=10,
                track_pitch=dif_block_header.TrackPitch.STANDARD_PLAY,
                pilot_frame=0,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_1=dif_block_header.ApplicationID1.CONSUMER_DIGITAL_VCR,
                application_id_2=dif_block_header.ApplicationID2.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
            ),
            file_info=NTSC_FILE,
        ),
        HeaderBlockBinaryTestCase(
            name="basic test: long play, NTSC, consumer format, first header, pilot 0",
            input=f"1F 07 00  3F 48 78 78 78 {TRAILER}",
            parsed=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=10,
                track_pitch=dif_block_header.TrackPitch.LONG_PLAY,
                pilot_frame=0,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_1=dif_block_header.ApplicationID1.CONSUMER_DIGITAL_VCR,
                application_id_2=dif_block_header.ApplicationID2.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
            ),
            file_info=NTSC_FILE,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_header_block_binary(tc: HeaderBlockBinaryTestCase) -> None:
    parsed = block_parser.parse_binary(bytes.fromhex(tc.input), tc.file_info)
    assert parsed == tc.parsed
    updated = parsed.to_binary(tc.file_info)
    assert updated == bytes.fromhex(tc.input)


@dataclass
class HeaderBlockValidateTestCase:
    name: str
    input: dif_block_header.Header
    failure: str
    file_info: dv_file_info.DVFileInfo


@pytest.mark.parametrize(
    "tc",
    [
        HeaderBlockValidateTestCase(
            name="invalid DIF sequence count",
            input=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=9,
                track_pitch=dif_block_header.TrackPitch.STANDARD_PLAY,
                pilot_frame=1,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_1=dif_block_header.ApplicationID1.CONSUMER_DIGITAL_VCR,
                application_id_2=dif_block_header.ApplicationID2.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
            ),
            failure="DIF header block must specify sequence count of 10 or 12.",
            file_info=NTSC_FILE,
        ),
        HeaderBlockValidateTestCase(
            name="DIF sequence count does not match system",
            input=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=12,
                track_pitch=dif_block_header.TrackPitch.STANDARD_PLAY,
                pilot_frame=1,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_1=dif_block_header.ApplicationID1.CONSUMER_DIGITAL_VCR,
                application_id_2=dif_block_header.ApplicationID2.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
            ),
            failure="DIF header block does not match with expected system SYS_525_60.",
            file_info=NTSC_FILE,
        ),
        HeaderBlockValidateTestCase(
            name="partial track information: no track pitch",
            input=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=10,
                track_pitch=None,
                pilot_frame=1,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_1=dif_block_header.ApplicationID1.CONSUMER_DIGITAL_VCR,
                application_id_2=dif_block_header.ApplicationID2.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
            ),
            failure="Track pitch and pilot frame must be both present or absent together.",
            file_info=NTSC_FILE,
        ),
        HeaderBlockValidateTestCase(
            name="partial track information: no pilot frame",
            input=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=10,
                track_pitch=dif_block_header.TrackPitch.STANDARD_PLAY,
                pilot_frame=None,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_1=dif_block_header.ApplicationID1.CONSUMER_DIGITAL_VCR,
                application_id_2=dif_block_header.ApplicationID2.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
            ),
            failure="Track pitch and pilot frame must be both present or absent together.",
            file_info=NTSC_FILE,
        ),
        HeaderBlockValidateTestCase(
            name="negative pilot frame",
            input=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=10,
                track_pitch=dif_block_header.TrackPitch.STANDARD_PLAY,
                pilot_frame=-1,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_1=dif_block_header.ApplicationID1.CONSUMER_DIGITAL_VCR,
                application_id_2=dif_block_header.ApplicationID2.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
            ),
            failure="DIF header block must specify a pilot frame of 0 or 1.",
            file_info=NTSC_FILE,
        ),
        HeaderBlockValidateTestCase(
            name="pilot frame high",
            input=dif_block_header.Header(
                block_id=dif_block.BlockID(
                    type=dif_block.BlockType.HEADER,
                    sequence=0xF,
                    channel=0,
                    dif_sequence=0,
                    dif_block=0,
                ),
                video_frame_dif_sequence_count=10,
                track_pitch=dif_block_header.TrackPitch.STANDARD_PLAY,
                pilot_frame=2,
                application_id_track=dif_block_header.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                application_id_1=dif_block_header.ApplicationID1.CONSUMER_DIGITAL_VCR,
                application_id_2=dif_block_header.ApplicationID2.CONSUMER_DIGITAL_VCR,
                application_id_3=dif_block_header.ApplicationID3.CONSUMER_DIGITAL_VCR,
            ),
            failure="DIF header block must specify a pilot frame of 0 or 1.",
            file_info=NTSC_FILE,
        ),
    ],
    ids=lambda tc: tc.name,
)
def test_header_block_validate_write(tc: HeaderBlockValidateTestCase) -> None:
    """Test validation failures when writing a header block to binary."""
    with pytest.raises(dif_block.DIFBlockError, match=tc.failure):
        tc.input.to_binary(tc.file_info)


def test_header_block_validate_read() -> None:
    """Test validation failures when reading a header block from binary.

    This is just a quick test to make sure the validation happens; most rules are tested in
    test_header_block_validate_write.
    """
    failure = "DIF header block does not match with expected system SYS_525_60."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  BF 78 78 78 78 {TRAILER}"), NTSC_FILE
        )

    # also check the failure branches in parse_binary
    failure = "Zero bit in DIF header block is unexpectedly not zero."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  7F 78 78 78 78 {TRAILER}"), NTSC_FILE
        )

    failure = "Reserved bits in DIF header block are unexpectedly in use."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  3F 70 78 78 78 {TRAILER}"), NTSC_FILE
        )

    failure = "Reserved bits in DIF header block are unexpectedly in use."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  3F 78 70 78 78 {TRAILER}"), NTSC_FILE
        )

    failure = "Reserved bits in DIF header block are unexpectedly in use."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  3F 78 78 70 78 {TRAILER}"), NTSC_FILE
        )

    failure = "Reserved bits in DIF header block are unexpectedly in use."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  3F 78 78 78 70 {TRAILER}"), NTSC_FILE
        )

    failure = "Unexpected values in the track information area of the DIF header block."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  3F A8 78 78 78 {TRAILER}"), NTSC_FILE
        )

    failure = "Transmitting flags for some DIF blocks are off in the DIF header block."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  3F 78 F8 78 78 {TRAILER}"), NTSC_FILE
        )

    failure = "Transmitting flags for some DIF blocks are off in the DIF header block."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  3F 78 78 F8 78 {TRAILER}"), NTSC_FILE
        )

    failure = "Transmitting flags for some DIF blocks are off in the DIF header block."
    with pytest.raises(dif_block.DIFBlockError, match=failure):
        dif_block_header.Header.parse_binary(
            bytes.fromhex(f"1F 07 00  3F 78 78 78 F8 {TRAILER}"), NTSC_FILE
        )