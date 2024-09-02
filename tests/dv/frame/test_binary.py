from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

import pytest

import video_tools.dv.block as block
import video_tools.dv.file.info as dv_file_info
import video_tools.dv.frame as frame
import video_tools.dv.pack as pack

TESTDATA_DIR = Path(__file__).parent / "testdata"


@dataclass(kw_only=True)
class FileTestCase:
    # This test works by:
    # 1.  Read and parse input DV file.  It must have exactly one frame.
    #     a.  Assert that it matches expected parsed frame.Data (without actual audio/video data).
    #     b.  Spot check assertions against audio and video data.
    # 2.  Write the frame.Data back to binary.
    #     a.  Assert that the rewritten binary matches expected:
    #     b.  If the input file was perfect and doesn't have any incoherencies that are expected to
    #         be fixed, then leave "output" as None.  The test will assert that the output bytes
    #         match the input file - proving that a round trip has modified exactly nothing.
    #     c.  If the input file had some incoherencies that we expect to be fixing, then set the
    #         output file to the expected output.
    # 3.  Read the rewritten binary back to a second frame.Data.
    #     a.  Assert that this matches the first frame.Data, proving that fixing any incoherencies
    #         during the data write process did not materially change the frame.Data.
    #
    # More about output files and assertion failures on the binary frame data:
    # Assertion failures when binary frame data does not match will be unintelligible.  The
    # recommended procedure when debugging these failures is as follows:
    # 1.  Write debug files using `pytest --write-debug`.  This will write testdata/*.debug.dv files
    #     that are the result of step 2, above.
    # 2.  For each block type in [HEADER, SUBCODE, VAUX, AUDIO, VIDEO] for the failing test case:
    #     a.  Dump both the original input file and the debug file using the dv_dif_dump utility in
    #         this repository, and redirect the output:
    #             dv_dif_dump --block-type [TYPE] [input].dv > [input].[TYPE].txt
    #             dv_dif_dump --block-type [TYPE] [debug].dv > [debug].[TYPE].txt
    #     b.  Use your favorite file comparison utility to compare the two text files.  Investigate
    #         any differences.  Use the IEC 61834 standard and other standards to decode data around
    #         locations that you observe differences.
    #     c.  If the differences are due to a bug, then fix the bug.  However, if the differences
    #         are expected (and you are 100% CERTAIN of this), then rename the debug file to an
    #         appropriate name, and specify it as the output file for the test case.

    input: str  # filename in testdata/
    parsed: frame.Data
    # spot checking of audio and video data.  indexed by DIF channel, DIF sequence, block number
    audio_samples: list[tuple[int, int, int, str]]
    video_samples: list[tuple[int, int, int, str]]
    output: str | None = None  # filename in testdata/


@pytest.mark.parametrize(
    "tc",
    [
        # ===== Real frames that I have captured from a Sony DCR-TRV460 =====
        FileTestCase(
            # This is a capture from a very recent recording I made with this Sony.  It basically
            # has no errors in it.
            input="sony_perfect.dv",
            parsed=frame.Data(
                # General information
                sequence=0x8,
                # DIF block: header data
                header_video_frame_dif_sequence_count=10,
                header_track_pitch=block.TrackPitch.STANDARD_PLAY,
                header_pilot_frame=0,
                header_application_id_track=block.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                header_application_id_1=block.ApplicationID1.CONSUMER_DIGITAL_VCR,
                header_application_id_2=block.ApplicationID2.CONSUMER_DIGITAL_VCR,
                header_application_id_3=block.ApplicationID3.CONSUMER_DIGITAL_VCR,
                # DIF block: subcode data: ID parts
                subcode_index=False,
                subcode_skip=False,
                subcode_picture=False,
                subcode_application_id_track=block.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                subcode_application_id_3=block.ApplicationID3.CONSUMER_DIGITAL_VCR,
                subcode_absolute_track_numbers=[[800, 801, 802, 803, 804, 805, 806, 807, 808, 809]],
                subcode_blank_flag=block.BlankFlag.CONTINUOUS,
                # DIF block: subcode data: packs
                subcode_pack_types=[
                    [
                        # first 5 sequences:
                        *[[0x13] * 12] * 5,
                        # second 5 sequences:
                        *[[0x13, 0x62, 0x63] * 4] * 5,
                    ],
                ],
                subcode_title_timecode=pack.TitleTimecode(
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
                subcode_title_binary_group=pack.TitleBinaryGroup(),
                subcode_vaux_recording_date=pack.VAUXRecordingDate(
                    year=2024, month=7, day=8, reserved=0x3
                ),
                subcode_vaux_recording_time=pack.VAUXRecordingTime(
                    hour=19,
                    minute=55,
                    second=58,
                    drop_frame=True,
                    color_frame=pack.ColorFrame.SYNCHRONIZED,
                    polarity_correction=pack.PolarityCorrection.ODD,
                    binary_group_flags=0x7,
                ),
                subcode_aaux_recording_date=pack.AAUXRecordingDate(),
                subcode_aaux_recording_time=pack.AAUXRecordingTime(),
                # DIF block: VAUX data
                vaux_pack_types=[
                    [
                        [*[0x70, 0x71, 0x7F], *[0xFF] * 36, *[0x60, 0x61, 0x62, 0x63], *[0xFF] * 2],
                        *[
                            [0x60, 0x61, 0x62, 0x63, *[0xFF] * 41],
                            [*[0xFF] * 39, 0x60, 0x61, 0x62, 0x63, *[0xFF] * 2],
                        ]
                        * 4,
                        [0x60, 0x61, 0x62, 0x63, *[0xFF] * 41],
                    ],
                ],
                vaux_source=pack.VAUXSource(
                    source_code=pack.SourceCode.CAMERA,
                    source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                    field_count=60,
                    bw_flag=pack.BlackAndWhiteFlag.COLOR,
                    color_frames_id_valid=False,
                    color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
                ),
                vaux_source_control=pack.VAUXSourceControl(
                    broadcast_system=0x0,
                    display_mode=0x0,
                    frame_field=pack.FrameField.BOTH,
                    first_second=1,
                    frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                    interlaced=True,
                    still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                    still_camera_picture=False,
                    copy_protection=pack.CopyProtection.NO_RESTRICTION,
                    input_source=pack.InputSource.ANALOG,
                    compression_count=pack.CompressionCount.CMP_1,
                    recording_start_point=False,
                    recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                    genre_category=0x7F,
                    reserved=0x1,
                ),
                vaux_recording_date=pack.VAUXRecordingDate(year=2024, month=7, day=8, reserved=0x3),
                vaux_recording_time=pack.VAUXRecordingTime(
                    hour=19,
                    minute=55,
                    second=58,
                    drop_frame=True,
                    color_frame=pack.ColorFrame.SYNCHRONIZED,
                    polarity_correction=pack.PolarityCorrection.ODD,
                    binary_group_flags=0x7,
                ),
                vaux_binary_group=pack.VAUXBinaryGroup(),
                vaux_camera_consumer_1=pack.CameraConsumer1(
                    auto_exposure_mode=pack.AutoExposureMode.FULL_AUTOMATIC,
                    iris=1.5,
                    auto_gain_control=0x7,
                    white_balance_mode=pack.WhiteBalanceMode.AUTOMATIC,
                    focus_mode=pack.FocusMode.MANUAL,
                ),
                vaux_camera_consumer_2=pack.CameraConsumer2(
                    vertical_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                    horizontal_panning_direction=(
                        pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING
                    ),
                    image_stabilizer_on=True,
                    electric_zoom_on=False,
                ),
                vaux_camera_shutter=pack.CameraShutter(shutter_speed_consumer=0x9D),
                # DIF block: AAUX
                aaux_pack_types=[
                    [
                        *[
                            [*[0xFF] * 3, 0x50, 0x51, 0x52, 0x53, *[0xFF] * 2],
                            [0x50, 0x51, 0x52, 0x53, *[0xFF] * 5],
                        ]
                        * 5,
                    ]
                ],
                aaux_source=[
                    [
                        pack.AAUXSource(
                            sample_frequency=32000,
                            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
                            audio_samples_per_frame=1068,
                            locked_mode=pack.LockedMode.UNLOCKED,
                            stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                            audio_block_channel_count=2,
                            audio_mode=0x0,
                            audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                            multi_language=False,
                            source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                            field_count=60,
                            emphasis_on=False,
                            emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
                        ),
                        pack.AAUXSource(
                            sample_frequency=32000,
                            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
                            audio_samples_per_frame=1068,
                            locked_mode=pack.LockedMode.UNLOCKED,
                            stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                            audio_block_channel_count=2,
                            audio_mode=0xF,  # invalid
                            audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                            multi_language=False,
                            source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                            field_count=60,
                            emphasis_on=False,
                            emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
                        ),
                    ]
                ],
                aaux_source_control=[
                    [
                        pack.AAUXSourceControl(
                            copy_protection=pack.CopyProtection.NO_RESTRICTION,
                            input_source=pack.InputSource.ANALOG,
                            compression_count=pack.CompressionCount.CMP_1,
                            recording_start_point=False,
                            recording_end_point=False,
                            recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                            genre_category=0x7F,
                            direction=pack.Direction.FORWARD,
                            playback_speed=Fraction(1),
                            reserved=0x1,
                        ),
                        pack.AAUXSourceControl(
                            copy_protection=pack.CopyProtection.NO_RESTRICTION,
                            input_source=pack.InputSource.ANALOG,
                            compression_count=pack.CompressionCount.CMP_1,
                            recording_start_point=False,
                            recording_end_point=False,
                            recording_mode=pack.AAUXRecordingMode.INVALID,
                            genre_category=0x7F,
                            direction=pack.Direction.FORWARD,
                            playback_speed=Fraction(1),
                            reserved=0x1,
                        ),
                    ]
                ],
                aaux_recording_date=[
                    [pack.AAUXRecordingDate(year=2024, month=7, day=8, reserved=0x3)] * 2
                ],
                aaux_recording_time=[
                    [
                        pack.AAUXRecordingTime(
                            hour=19,
                            minute=55,
                            second=58,
                            drop_frame=True,
                            color_frame=pack.ColorFrame.SYNCHRONIZED,
                            polarity_correction=pack.PolarityCorrection.ODD,
                            binary_group_flags=0x7,
                        )
                    ]
                    * 2
                ],
                aaux_binary_group=[[pack.AAUXBinaryGroup(), pack.AAUXBinaryGroup()]],
                # DIF block: audio data
                audio_data=None,
                audio_data_errors=[[[False] * 9] * 10],
                audio_data_error_summary=[[0.0, 0.0]],
                # DIF block: video data
                video_data=None,
                video_data_errors=[[[False] * 135] * 10],
                video_data_error_summary=0.0,
            ),
            audio_samples=[
                (
                    0,
                    3,
                    5,
                    "ACC4905455E04A450DA7AB1021E3DC2441E5574AA7B4B56E9C9FBB5551D74540A66464C8"
                    "9A993402070C5B5467BBBE69A2A67E504C26B7E41C503BEEBABDD1ABB740433CE8000000",
                ),
                (0, 5, 3, "".join(["00"] * 72)),
            ],
            video_samples=[
                (
                    0,
                    5,
                    2,
                    "09E6950761633050C5041E0719DA1AE89497212E0E2808880B47078234E7805414D41526"
                    "A54F22B23CF0EEE790630227050A0468107028FD3A051A40D30F733E334C87FD234B9B4B"
                    "E8074432CE",
                ),
            ],
        ),
        FileTestCase(
            # This was a 24-year-old tape that was transferred using the Sony DCR-TRV460.  It was
            # recorded on a much older Sony Digital8 camcorder.  This frame has good video/audio
            # data, but the subcode areas are a big mess, with lots of intermittent dropouts
            # leading to many incoherencies in the subcode packs.  Some "valid" subcode packs even
            # have the wrong timecode (off by a frame).
            input="sony_subcode_errors.dv",
            # some subcode incoherencies are fixed in the output; other DIF blocks are unchanged:
            output="sony_subcode_errors.output.dv",
            parsed=frame.Data(
                # General information
                sequence=0xB,
                # DIF block: header data
                header_video_frame_dif_sequence_count=10,
                header_track_pitch=block.TrackPitch.STANDARD_PLAY,
                header_pilot_frame=0,
                header_application_id_track=block.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                header_application_id_1=block.ApplicationID1.CONSUMER_DIGITAL_VCR,
                header_application_id_2=block.ApplicationID2.CONSUMER_DIGITAL_VCR,
                header_application_id_3=block.ApplicationID3.CONSUMER_DIGITAL_VCR,
                # DIF block: subcode data: ID parts
                subcode_index=False,
                subcode_skip=False,
                subcode_picture=False,
                subcode_application_id_track=block.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                subcode_application_id_3=block.ApplicationID3.CONSUMER_DIGITAL_VCR,
                subcode_absolute_track_numbers=[
                    [660, None, 662, 663, 664, 665, 666, 667, 668, 669]
                ],
                subcode_blank_flag=block.BlankFlag.CONTINUOUS,
                # DIF block: subcode data: packs
                subcode_pack_types=[
                    [
                        # Did I mention this has a lot of subcode dropouts?
                        [*[0x13] * 9, *[0xFF] * 3],
                        [*[0xFF] * 12],
                        [*[0x13] * 9, *[0xFF] * 3],
                        [*[0x13] * 8, *[0xFF] * 4],
                        [*[0x13] * 10, *[0xFF] * 2],
                        [0x13, 0x62, 0x63] * 4,
                        [0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0xFF, 0xFF],
                        [0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0xFF, 0xFF, 0xFF, 0xFF],
                        [0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0xFF, 0xFF, 0xFF],
                        [0xFF, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0xFF],
                    ],
                ],
                subcode_title_timecode=pack.TitleTimecode(
                    hour=0,
                    minute=0,
                    second=2,
                    frame=6,
                    drop_frame=True,
                    color_frame=pack.ColorFrame.SYNCHRONIZED,
                    polarity_correction=pack.PolarityCorrection.ODD,
                    binary_group_flags=0x7,
                    blank_flag=pack.BlankFlag.CONTINUOUS,
                ),
                subcode_title_binary_group=pack.TitleBinaryGroup(),
                subcode_vaux_recording_date=pack.VAUXRecordingDate(
                    year=2000, month=12, day=3, reserved=0x3
                ),
                subcode_vaux_recording_time=pack.VAUXRecordingTime(
                    hour=10,
                    minute=15,
                    second=59,
                    drop_frame=True,
                    color_frame=pack.ColorFrame.SYNCHRONIZED,
                    polarity_correction=pack.PolarityCorrection.ODD,
                    binary_group_flags=0x7,
                ),
                subcode_aaux_recording_date=pack.AAUXRecordingDate(),
                subcode_aaux_recording_time=pack.AAUXRecordingTime(),
                # DIF block: VAUX data
                vaux_pack_types=[
                    [
                        [*[0x70, 0x71, 0x7F], *[0xFF] * 36, *[0x60, 0x61, 0x62, 0x63], *[0xFF] * 2],
                        *[
                            [0x60, 0x61, 0x62, 0x63, *[0xFF] * 41],
                            [*[0xFF] * 39, 0x60, 0x61, 0x62, 0x63, *[0xFF] * 2],
                        ]
                        * 4,
                        [0x60, 0x61, 0x62, 0x63, *[0xFF] * 41],
                    ],
                ],
                vaux_source=pack.VAUXSource(
                    source_code=pack.SourceCode.CAMERA,
                    source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                    field_count=60,
                    bw_flag=pack.BlackAndWhiteFlag.COLOR,
                    color_frames_id_valid=False,
                    color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
                ),
                vaux_source_control=pack.VAUXSourceControl(
                    broadcast_system=0x0,
                    display_mode=0x0,
                    frame_field=pack.FrameField.BOTH,
                    first_second=1,
                    frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                    interlaced=True,
                    still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                    still_camera_picture=False,
                    copy_protection=pack.CopyProtection.NO_RESTRICTION,
                    input_source=pack.InputSource.ANALOG,
                    compression_count=pack.CompressionCount.CMP_1,
                    recording_start_point=False,
                    recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                    genre_category=0x7F,
                    reserved=0x1,
                ),
                vaux_recording_date=pack.VAUXRecordingDate(
                    year=2000, month=12, day=3, reserved=0x3
                ),
                vaux_recording_time=pack.VAUXRecordingTime(
                    hour=10,
                    minute=15,
                    second=59,
                    drop_frame=True,
                    color_frame=pack.ColorFrame.SYNCHRONIZED,
                    polarity_correction=pack.PolarityCorrection.ODD,
                    binary_group_flags=0x7,
                ),
                vaux_binary_group=pack.VAUXBinaryGroup(),
                vaux_camera_consumer_1=pack.CameraConsumer1(
                    auto_exposure_mode=pack.AutoExposureMode.FULL_AUTOMATIC,
                    iris=16.0,
                    auto_gain_control=0x1,
                    white_balance_mode=pack.WhiteBalanceMode.AUTOMATIC,
                    focus_mode=pack.FocusMode.MANUAL,
                ),
                vaux_camera_consumer_2=pack.CameraConsumer2(
                    vertical_panning_direction=pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING,
                    horizontal_panning_direction=(
                        pack.PanningDirection.OPPOSITE_DIRECTION_OF_SCANNING
                    ),
                    image_stabilizer_on=True,
                    electric_zoom_on=False,
                ),
                vaux_camera_shutter=pack.CameraShutter(shutter_speed_consumer=0x9D),
                # DIF block: AAUX
                aaux_pack_types=[
                    [
                        *[
                            [*[0xFF] * 3, 0x50, 0x51, 0x52, 0x53, *[0xFF] * 2],
                            [0x50, 0x51, 0x52, 0x53, *[0xFF] * 5],
                        ]
                        * 5,
                    ]
                ],
                aaux_source=[
                    [
                        pack.AAUXSource(
                            sample_frequency=32000,
                            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
                            audio_samples_per_frame=1068,
                            locked_mode=pack.LockedMode.UNLOCKED,
                            stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                            audio_block_channel_count=2,
                            audio_mode=0x0,
                            audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                            multi_language=False,
                            source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                            field_count=60,
                            emphasis_on=False,
                            emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
                        ),
                        pack.AAUXSource(
                            sample_frequency=32000,
                            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
                            audio_samples_per_frame=1068,
                            locked_mode=pack.LockedMode.UNLOCKED,
                            stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                            audio_block_channel_count=2,
                            audio_mode=0xF,  # invalid
                            audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                            multi_language=False,
                            source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                            field_count=60,
                            emphasis_on=False,
                            emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
                        ),
                    ]
                ],
                aaux_source_control=[
                    [
                        pack.AAUXSourceControl(
                            copy_protection=pack.CopyProtection.NO_RESTRICTION,
                            input_source=pack.InputSource.ANALOG,
                            compression_count=pack.CompressionCount.CMP_1,
                            recording_start_point=False,
                            recording_end_point=False,
                            recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                            genre_category=0x7F,
                            direction=pack.Direction.FORWARD,
                            playback_speed=Fraction(1),
                            reserved=0x1,
                        ),
                        pack.AAUXSourceControl(
                            copy_protection=pack.CopyProtection.NO_RESTRICTION,
                            input_source=pack.InputSource.ANALOG,
                            compression_count=pack.CompressionCount.CMP_1,
                            recording_start_point=False,
                            recording_end_point=False,
                            recording_mode=pack.AAUXRecordingMode.INVALID,
                            genre_category=0x7F,
                            direction=pack.Direction.FORWARD,
                            playback_speed=Fraction(1),
                            reserved=0x1,
                        ),
                    ]
                ],
                aaux_recording_date=[
                    [pack.AAUXRecordingDate(year=2000, month=12, day=3, reserved=0x3)] * 2
                ],
                aaux_recording_time=[
                    [
                        pack.AAUXRecordingTime(
                            hour=10,
                            minute=15,
                            second=59,
                            drop_frame=True,
                            color_frame=pack.ColorFrame.SYNCHRONIZED,
                            polarity_correction=pack.PolarityCorrection.ODD,
                            binary_group_flags=0x7,
                        )
                    ]
                    * 2
                ],
                aaux_binary_group=[[pack.AAUXBinaryGroup(), pack.AAUXBinaryGroup()]],
                # DIF block: audio data
                audio_data=None,
                audio_data_errors=[[[False] * 9] * 10],
                audio_data_error_summary=[[0.0, 0.0]],
                # DIF block: video data
                video_data=None,
                video_data_errors=[[[False] * 135] * 10],
                video_data_error_summary=0.0,
            ),
            audio_samples=[
                (
                    0,
                    3,
                    5,
                    "4D497AB4B231331ED8D3F2E84C434BCCD7E440418BB8B2320BEE68DDCFF8252A8FB9BDD1"
                    "3846D8343F2F343A82ACADAF535519B4AC61504A69C3BF123B4862AEAC22545428000000",
                ),
                (0, 5, 3, "".join(["00"] * 72)),
            ],
            video_samples=[
                (
                    0,
                    5,
                    2,
                    "0B380112A4D031973F90781AFC4690378D7E09C58681C1E69229C6FF05378AC90F1C50AE"
                    "3C17D74FE40B33370ADF5538DFC11A0EAE83A2691AE8134BB181C0C6C030471A2181BC80"
                    "F35BC3621E",
                ),
            ],
        ),
        FileTestCase(
            # This was from the same tape as "sony_subcode_errors.dv", but one of the heads was
            # having a much more difficult time.
            input="sony_head_clog.dv",
            # Expected changes in the binary output:
            # 1.  Incoherencies in the sequence number in DIF block IDs throughout the file are
            #     fixed.
            # 2.  Subcodes in zero-based sequence 4 don't have the "front half" bit set in the ID
            #     parts.  Apparently the tracks got mixed up somehow because this track also
            #     has timecode frame numbers that were from the previous frame.  Anyway, this
            #     invalid "front half" bit means that we throw away all the ID parts completely
            #     for that track.
            # 3.  Title Timecode packs in general have incoherencies which are resolved
            #     (unfortunately, to the wrong value of frame 12, not the correct frame 13).
            #
            # Header/VAUX/audio/video data remains unchanged, apart from the noted DIF block ID
            # sequence number changes.
            output="sony_head_clog.output.dv",
            parsed=frame.Data(
                # General information
                sequence=0xF,
                # DIF block: header data
                header_video_frame_dif_sequence_count=10,
                header_track_pitch=block.TrackPitch.STANDARD_PLAY,
                header_pilot_frame=0,
                header_application_id_track=block.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                header_application_id_1=block.ApplicationID1.CONSUMER_DIGITAL_VCR,
                header_application_id_2=block.ApplicationID2.CONSUMER_DIGITAL_VCR,
                header_application_id_3=block.ApplicationID3.CONSUMER_DIGITAL_VCR,
                # DIF block: subcode data: ID parts
                subcode_index=False,
                subcode_skip=False,
                subcode_picture=False,
                subcode_application_id_track=None,
                subcode_application_id_3=block.ApplicationID3.CONSUMER_DIGITAL_VCR,
                subcode_absolute_track_numbers=[
                    # the correct values should have been in range [130, 139]
                    [121, None, 132, None, None, None, 136, 137, 129, None]
                ],
                subcode_blank_flag=block.BlankFlag.CONTINUOUS,
                # DIF block: subcode data: packs
                subcode_pack_types=[
                    [
                        [*[0x13] * 11, 0xFF],
                        [*[0xFF] * 12],
                        [0xFF, *[0x13] * 9, *[0xFF] * 2],
                        [*[0xFF] * 12],
                        # this clearly isn't even the right track... 0x62 / 0x63 don't normally
                        # appear until the second half of the frame, but this is a track early:
                        [0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0xFF],
                        [*[0xFF] * 12],
                        [0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0xFF, 0xFF, 0xFF],
                        [0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0xFF],
                        [0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0x63, 0x13, 0x62, 0xFF],
                        [*[0xFF] * 12],
                    ],
                ],
                subcode_title_timecode=pack.TitleTimecode(
                    hour=0,
                    minute=0,
                    second=0,
                    frame=12,  # actually the wrong number, but for this frame, 12 was more common
                    drop_frame=True,
                    color_frame=pack.ColorFrame.SYNCHRONIZED,
                    polarity_correction=pack.PolarityCorrection.ODD,
                    binary_group_flags=0x7,
                    blank_flag=pack.BlankFlag.CONTINUOUS,
                ),
                subcode_title_binary_group=pack.TitleBinaryGroup(),
                subcode_vaux_recording_date=pack.VAUXRecordingDate(
                    year=2000, month=12, day=3, reserved=0x3
                ),
                subcode_vaux_recording_time=pack.VAUXRecordingTime(
                    hour=10,
                    minute=15,
                    second=57,
                    drop_frame=True,
                    color_frame=pack.ColorFrame.SYNCHRONIZED,
                    polarity_correction=pack.PolarityCorrection.ODD,
                    binary_group_flags=0x7,
                ),
                subcode_aaux_recording_date=pack.AAUXRecordingDate(),
                subcode_aaux_recording_time=pack.AAUXRecordingTime(),
                # DIF block: VAUX data
                vaux_pack_types=[
                    [
                        *[
                            [0xFF] * 45,
                            [0xFF] * 45,
                            [*[0xFF] * 39, 0x60, 0x61, 0x62, 0x63, *[0xFF] * 2],
                            [0x60, 0x61, 0x62, 0x63, *[0xFF] * 41],
                        ]
                        * 2,
                        [0xFF] * 45,
                        [0xFF] * 45,
                    ],
                ],
                vaux_source=pack.VAUXSource(
                    source_code=pack.SourceCode.CAMERA,
                    source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                    field_count=60,
                    bw_flag=pack.BlackAndWhiteFlag.COLOR,
                    color_frames_id_valid=False,
                    color_frames_id=pack.ColorFramesID.CLF_7_8_FIELD,
                ),
                vaux_source_control=pack.VAUXSourceControl(
                    broadcast_system=0x0,
                    display_mode=0x0,
                    frame_field=pack.FrameField.BOTH,
                    first_second=1,
                    frame_change=pack.FrameChange.DIFFERENT_FROM_PREVIOUS,
                    interlaced=True,
                    still_field_picture=pack.StillFieldPicture.TWICE_FRAME_TIME,
                    still_camera_picture=False,
                    copy_protection=pack.CopyProtection.NO_RESTRICTION,
                    input_source=pack.InputSource.ANALOG,
                    compression_count=pack.CompressionCount.CMP_1,
                    recording_start_point=False,
                    recording_mode=pack.VAUXRecordingMode.ORIGINAL,
                    genre_category=0x7F,
                    reserved=0x1,
                ),
                vaux_recording_date=pack.VAUXRecordingDate(
                    year=2000, month=12, day=3, reserved=0x3
                ),
                vaux_recording_time=pack.VAUXRecordingTime(
                    hour=10,
                    minute=15,
                    second=57,
                    drop_frame=True,
                    color_frame=pack.ColorFrame.SYNCHRONIZED,
                    polarity_correction=pack.PolarityCorrection.ODD,
                    binary_group_flags=0x7,
                ),
                vaux_binary_group=pack.VAUXBinaryGroup(),
                vaux_camera_consumer_1=pack.CameraConsumer1(),
                vaux_camera_consumer_2=pack.CameraConsumer2(),
                vaux_camera_shutter=pack.CameraShutter(),
                # DIF block: AAUX
                aaux_pack_types=[
                    [
                        [0xFF] * 9,
                        [0xFF] * 9,
                        [*[0xFF] * 3, 0x50, 0x51, 0x52, 0x53, *[0xFF] * 2],
                        [0x50, 0x51, 0x52, 0x53, *[0xFF] * 5],
                        [0xFF] * 9,
                        [0xFF] * 9,
                        [*[0xFF] * 3, 0x50, 0x51, 0x52, 0x53, *[0xFF] * 2],
                        [0x50, 0x51, 0x52, 0x53, *[0xFF] * 5],
                        [0xFF] * 9,
                        [0xFF] * 9,
                    ]
                ],
                aaux_source=[
                    [
                        pack.AAUXSource(
                            sample_frequency=32000,
                            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
                            audio_samples_per_frame=1068,
                            locked_mode=pack.LockedMode.UNLOCKED,
                            stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                            audio_block_channel_count=2,
                            audio_mode=0x0,
                            audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                            multi_language=False,
                            source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                            field_count=60,
                            emphasis_on=False,
                            emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
                        ),
                        pack.AAUXSource(
                            sample_frequency=32000,
                            quantization=pack.AudioQuantization.NONLINEAR_12_BIT,
                            audio_samples_per_frame=1068,
                            locked_mode=pack.LockedMode.UNLOCKED,
                            stereo_mode=pack.StereoMode.MULTI_STEREO_AUDIO,
                            audio_block_channel_count=2,
                            audio_mode=0xF,  # invalid
                            audio_block_pairing=pack.AudioBlockPairing.INDEPENDENT,
                            multi_language=False,
                            source_type=pack.SourceType.STANDARD_DEFINITION_COMPRESSED_CHROMA,
                            field_count=60,
                            emphasis_on=False,
                            emphasis_time_constant=pack.EmphasisTimeConstant.E_50_15,
                        ),
                    ]
                ],
                aaux_source_control=[
                    [
                        pack.AAUXSourceControl(
                            copy_protection=pack.CopyProtection.NO_RESTRICTION,
                            input_source=pack.InputSource.ANALOG,
                            compression_count=pack.CompressionCount.CMP_1,
                            recording_start_point=False,
                            recording_end_point=False,
                            recording_mode=pack.AAUXRecordingMode.ORIGINAL,
                            genre_category=0x7F,
                            direction=pack.Direction.FORWARD,
                            playback_speed=Fraction(1),
                            reserved=0x1,
                        ),
                        pack.AAUXSourceControl(
                            copy_protection=pack.CopyProtection.NO_RESTRICTION,
                            input_source=pack.InputSource.ANALOG,
                            compression_count=pack.CompressionCount.CMP_1,
                            recording_start_point=False,
                            recording_end_point=False,
                            recording_mode=pack.AAUXRecordingMode.INVALID,
                            genre_category=0x7F,
                            direction=pack.Direction.FORWARD,
                            playback_speed=Fraction(1),
                            reserved=0x1,
                        ),
                    ]
                ],
                aaux_recording_date=[
                    [pack.AAUXRecordingDate(year=2000, month=12, day=3, reserved=0x3)] * 2
                ],
                aaux_recording_time=[
                    [
                        pack.AAUXRecordingTime(
                            hour=10,
                            minute=15,
                            second=57,
                            drop_frame=True,
                            color_frame=pack.ColorFrame.SYNCHRONIZED,
                            polarity_correction=pack.PolarityCorrection.ODD,
                            binary_group_flags=0x7,
                        )
                    ]
                    * 2
                ],
                aaux_binary_group=[[pack.AAUXBinaryGroup(), pack.AAUXBinaryGroup()]],
                # DIF block: audio data
                audio_data=None,
                audio_data_errors=[
                    [
                        [True] * 9,
                        [True] * 9,
                        [False] * 9,
                        [False] * 9,
                        [True] * 9,
                        [True] * 9,
                        [False] * 9,
                        [False] * 9,
                        [True] * 9,
                        [True] * 9,
                    ]
                ],
                audio_data_error_summary=[[0.6, 0.6]],
                # DIF block: video data
                video_data=None,
                video_data_errors=[
                    [
                        [*[False, False, True, True, True] * 27],
                        [*[False, False, True, True, True] * 27],
                        [*[True, True, True, False, False] * 27],
                        [*[True, True, True, False, False] * 27],
                        [*[False, True, False, True, True] * 27],
                        [*[False, True, False, True, True] * 27],
                        [*[True, False, True, False, True] * 27],
                        [*[True, False, True, False, True] * 27],
                        [*[True, True, False, True, False] * 27],
                        [*[True, True, False, True, False] * 27],
                    ]
                ],
                video_data_error_summary=0.6,
            ),
            audio_samples=[
                (
                    0,
                    3,
                    5,
                    "423A052E2693453E779C9BD69F9A3B62638C52518C4744F4ACA5DCEE40863E0A44A4A4DF"
                    "5D5A6C2A416B51476BC5BEB4BEF7BA212885D3BF16261FF0AEAE782E496A5B5959000000",
                ),
                (0, 5, 3, "".join(["808000"] * 24)),
            ],
            video_samples=[
                (
                    0,
                    5,
                    2,
                    "0B3F0ADF468E27E0D33AB412345B433F045ADDA0EC00D0781CD73F44973E81125CE2EA1C"
                    "FD0038747099813E0D77978229C4F0ED1C01487E81E9104BB86F6F8D861E2318A7398AA7"
                    "C9D261CC00",
                ),
            ],
        ),
        FileTestCase(
            # A brief empty section of tape between two segments.
            input="sony_drop_frame.dv",
            parsed=frame.Data(
                # General information
                sequence=0xF,
                # DIF block: header data
                header_video_frame_dif_sequence_count=10,
                header_track_pitch=block.TrackPitch.STANDARD_PLAY,
                header_pilot_frame=0,
                header_application_id_track=block.ApplicationIDTrack.CONSUMER_DIGITAL_VCR,
                header_application_id_1=block.ApplicationID1.CONSUMER_DIGITAL_VCR,
                header_application_id_2=block.ApplicationID2.CONSUMER_DIGITAL_VCR,
                header_application_id_3=block.ApplicationID3.CONSUMER_DIGITAL_VCR,
                # DIF block: subcode data: ID parts
                subcode_index=None,
                subcode_skip=None,
                subcode_picture=None,
                subcode_application_id_track=None,
                subcode_application_id_3=None,
                subcode_absolute_track_numbers=[[None] * 10],
                subcode_blank_flag=None,
                # DIF block: subcode data: packs
                subcode_pack_types=[[[0xFF] * 12] * 10],
                subcode_title_timecode=pack.TitleTimecode(),
                subcode_title_binary_group=pack.TitleBinaryGroup(),
                subcode_vaux_recording_date=pack.VAUXRecordingDate(),
                subcode_vaux_recording_time=pack.VAUXRecordingTime(),
                subcode_aaux_recording_date=pack.AAUXRecordingDate(),
                subcode_aaux_recording_time=pack.AAUXRecordingTime(),
                # DIF block: VAUX data
                vaux_pack_types=[[[0xFF] * 45] * 10],
                vaux_source=pack.VAUXSource(),
                vaux_source_control=pack.VAUXSourceControl(),
                vaux_recording_date=pack.VAUXRecordingDate(),
                vaux_recording_time=pack.VAUXRecordingTime(),
                vaux_binary_group=pack.VAUXBinaryGroup(),
                vaux_camera_consumer_1=pack.CameraConsumer1(),
                vaux_camera_consumer_2=pack.CameraConsumer2(),
                vaux_camera_shutter=pack.CameraShutter(),
                # DIF block: AAUX
                aaux_pack_types=[[[0xFF] * 9] * 10],
                aaux_source=[[pack.AAUXSource()] * 2],
                aaux_source_control=[[pack.AAUXSourceControl()] * 2],
                aaux_recording_date=[[pack.AAUXRecordingDate()] * 2],
                aaux_recording_time=[[pack.AAUXRecordingTime()] * 2],
                aaux_binary_group=[[pack.AAUXBinaryGroup(), pack.AAUXBinaryGroup()]],
                # DIF block: audio data
                audio_data=None,
                audio_data_errors=[[[True] * 9] * 10],
                audio_data_error_summary=[[1.0, 1.0]],
                # DIF block: video data
                video_data=None,
                video_data_errors=[[[True] * 135] * 10],
                video_data_error_summary=1.0,
            ),
            audio_samples=[
                (0, 3, 5, "".join(["808000"] * 24)),
                (0, 5, 3, "".join(["808000"] * 24)),
            ],
            video_samples=[
                (
                    0,
                    5,
                    2,
                    "A6BBEF6977A3F29232D7A5690301C2C52BAF32C88082ED101717010786CCEF5FAFD81D52"
                    "4A07F250D26818E1EFE5F5474D02EB07BA281C745E0EB9F23F3843787607B6F5B46472A9"
                    "A5BDEDC431",
                ),
            ],
        ),
    ],
    ids=lambda tc: tc.input,
)
def test_binary(tc: FileTestCase, write_debug: bool) -> None:
    """Test round trip of a block from binary, to parsed, and then back to binary."""

    # 1.  Read and parse input DV file
    with open(TESTDATA_DIR / tc.input, mode="rb") as input_file:
        file_info = dv_file_info.read_dv_file_info(input_file)

        input_file.seek(0)
        input_bytes = input_file.read()

    parsed = frame.parse_binary(input_bytes, file_info)

    # 1 Assertions:  Assert that it matches expected parsed frame.Data and audio/video samples.

    # Don't include audio/video data in our comparison.
    no_data = replace(parsed, audio_data=None, video_data=None)
    assert no_data == tc.parsed

    # Spot checking audio/video samples
    assert parsed.audio_data is not None
    for channel, sequence, blk, data in tc.audio_samples:
        assert parsed.audio_data[channel][sequence][blk] == bytes.fromhex(data)
    assert parsed.video_data is not None
    for channel, sequence, blk, data in tc.video_samples:
        assert parsed.video_data[channel][sequence][blk] == bytes.fromhex(data)

    # 2.  Write the frame.Data back to binary.

    output_bytes = frame.to_binary(parsed, file_info)
    if write_debug:
        # Write the reserialized frame bytes to a debug file if requested.
        with open(TESTDATA_DIR / (tc.input + ".debug.dv"), mode="wb") as debug_file:
            debug_file.write(output_bytes)
        # Fail the tests if this debug flag was given
        assert not "Tests cannot pass if --write-debug is used."

    # 2a.  Assert that the output contains expected output bytes.
    with open(TESTDATA_DIR / (tc.output if tc.output else tc.input), mode="rb") as output_file:
        expected_output_bytes = output_file.read()
        # See comments in FileTestCase for advice on debugging this assertion failure.
        assert output_bytes == expected_output_bytes

        # 3.  Read the rewritten binary back to a second frame.Data and assert it didn't change
        #     from the first frame.Data.
        output_file.seek(0)
        output_file_info = dv_file_info.read_dv_file_info(output_file)
        output_parsed = frame.parse_binary(output_bytes, output_file_info)

        assert output_file_info == file_info
        assert output_parsed == parsed
