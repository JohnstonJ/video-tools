"""Functions for going to/from binary frames."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TypeVar, cast

import video_tools.dv.block as block
import video_tools.dv.data_util as du
import video_tools.dv.file.info as dv_file_info
import video_tools.dv.pack as pack

from .data import (
    BLOCK_NUMBER,
    BLOCK_TRANSMISSION_ORDER,
    Data,
    FrameError,
)


def parse_binary(frame_bytes: bytes, file_info: dv_file_info.Info) -> Data:
    assert len(frame_bytes) == file_info.video_frame_size

    state = _BinaryParseState.init_parse_state(file_info)
    b_start = 0  # current block starting position

    for channel in range(file_info.video_frame_channel_count):
        for sequence in range(file_info.video_frame_dif_sequence_count):
            for blk in range(len(BLOCK_TRANSMISSION_ORDER)):
                # Parse the block
                try:
                    state.parse_block(
                        channel,
                        sequence,
                        blk,
                        frame_bytes[b_start : b_start + block.BLOCK_SIZE],
                        file_info,
                    )
                except Exception as e:
                    raise FrameError(
                        f"Error while parsing input binary data for channel {channel}, "
                        f"DIF sequence/track {sequence}, block {blk}."
                    ) from e

                b_start += block.BLOCK_SIZE

    # Check that lists were fully filled out.  This makes it safe to cast the list types
    # later on.
    state.assert_elements_filled()

    # Calculate audio/video errors
    audio_data_errors, audio_data_error_summary = state.calc_audio_errors(file_info)
    video_data_errors, video_data_error_summary = state.calc_video_errors()

    dat = Data(
        sequence=_common_value(state.sequence),
        # Header block
        header_video_frame_dif_sequence_count=_common_value(state.header_dif_sequence_count),
        header_track_pitch=_common_value_default_none(state.header_track_pitch),
        header_pilot_frame=_common_value_default_none(state.header_pilot_frame),
        header_application_id_track=_common_value_default_none(state.header_application_id_track),
        header_application_id_1=_common_value_default_none(state.header_application_id_1),
        header_application_id_2=_common_value_default_none(state.header_application_id_2),
        header_application_id_3=_common_value_default_none(state.header_application_id_3),
        # Subcode block: ID part
        subcode_index=_common_value_default_none(state.subcode_index),
        subcode_skip=_common_value_default_none(state.subcode_skip),
        subcode_picture=_common_value_default_none(state.subcode_picture),
        subcode_application_id_track=_common_value_default_none(state.subcode_application_id_track),
        subcode_application_id_3=_common_value_default_none(state.subcode_application_id_3),
        subcode_absolute_track_numbers=[
            [
                _common_absolute_track_number(
                    state.subcode_absolute_track_numbers_2[channel][sequence],
                    state.subcode_absolute_track_numbers_1[channel][sequence],
                    state.subcode_absolute_track_numbers_0[channel][sequence],
                )
                for sequence in range(len(state.subcode_absolute_track_numbers_0[channel]))
            ]
            for channel in range(len(state.subcode_absolute_track_numbers_0))
        ],
        subcode_blank_flag=_common_value_default_none(state.subcode_blank_flag),
        # Subcode block: packs part
        subcode_pack_types=cast(list[list[list[int]]], state.subcode_pack_types),
        subcode_title_timecode=_common_value_default(
            state.subcode_title_timecode, pack.TitleTimecode()
        ),
        subcode_title_binary_group=_common_value_default(
            state.subcode_title_binary_group, pack.TitleBinaryGroup()
        ),
        subcode_vaux_recording_date=_common_value_default(
            state.subcode_vaux_recording_date, pack.VAUXRecordingDate()
        ),
        subcode_vaux_recording_time=_common_value_default(
            state.subcode_vaux_recording_time, pack.VAUXRecordingTime()
        ),
        subcode_aaux_recording_date=_common_value_default(
            state.subcode_aaux_recording_date, pack.AAUXRecordingDate()
        ),
        subcode_aaux_recording_time=_common_value_default(
            state.subcode_aaux_recording_time, pack.AAUXRecordingTime()
        ),
        # VAUX block
        vaux_pack_types=cast(list[list[list[int]]], state.vaux_pack_types),
        vaux_source=_common_value_default(state.vaux_source, pack.VAUXSource()),
        vaux_source_control=_common_value_default(
            state.vaux_source_control, pack.VAUXSourceControl()
        ),
        vaux_recording_date=_common_value_default(
            state.vaux_recording_date, pack.VAUXRecordingDate()
        ),
        vaux_recording_time=_common_value_default(
            state.vaux_recording_time, pack.VAUXRecordingTime()
        ),
        vaux_binary_group=_common_value_default(state.vaux_binary_group, pack.VAUXBinaryGroup()),
        vaux_camera_consumer_1=_common_value_default(
            state.vaux_camera_consumer_1, pack.CameraConsumer1()
        ),
        vaux_camera_consumer_2=_common_value_default(
            state.vaux_camera_consumer_2, pack.CameraConsumer2()
        ),
        vaux_camera_shutter=_common_value_default(state.vaux_camera_shutter, pack.CameraShutter()),
        # Audio block: AAUX
        aaux_pack_types=cast(list[list[list[int]]], state.aaux_pack_types),
        aaux_source=[
            [
                _common_value_default(state.aaux_source[channel][audio_block], pack.AAUXSource())
                for audio_block in range(len(state.aaux_source[channel]))
            ]
            for channel in range(len(state.aaux_source))
        ],
        aaux_source_control=[
            [
                _common_value_default(
                    state.aaux_source_control[channel][audio_block], pack.AAUXSourceControl()
                )
                for audio_block in range(len(state.aaux_source_control[channel]))
            ]
            for channel in range(len(state.aaux_source_control))
        ],
        aaux_recording_date=[
            [
                _common_value_default(
                    state.aaux_recording_date[channel][audio_block], pack.AAUXRecordingDate()
                )
                for audio_block in range(len(state.aaux_recording_date[channel]))
            ]
            for channel in range(len(state.aaux_recording_date))
        ],
        aaux_recording_time=[
            [
                _common_value_default(
                    state.aaux_recording_time[channel][audio_block], pack.AAUXRecordingTime()
                )
                for audio_block in range(len(state.aaux_recording_time[channel]))
            ]
            for channel in range(len(state.aaux_recording_time))
        ],
        aaux_binary_group=[
            [
                _common_value_default(
                    state.aaux_binary_group[channel][audio_block], pack.AAUXBinaryGroup()
                )
                for audio_block in range(len(state.aaux_binary_group[channel]))
            ]
            for channel in range(len(state.aaux_binary_group))
        ],
        # Audio block: audio data
        audio_data=[
            [
                [cast(block.Audio, block_audio).audio_data for block_audio in sequence_audio]
                for sequence_audio in channel_audio
            ]
            for channel_audio in state.audio_blocks
        ],
        audio_data_errors=audio_data_errors,
        audio_data_error_summary=audio_data_error_summary,
        # Video block: video data
        video_data=[
            [
                [cast(block.Video, block_video).video_data for block_video in sequence_video]
                for sequence_video in channel_video
            ]
            for channel_video in state.video_blocks
        ],
        video_data_errors=video_data_errors,
        video_data_error_summary=video_data_error_summary,
    )
    dat.validate(file_info)
    return dat


T = TypeVar("T")
T_obj = TypeVar("T_obj", bound=object)

# Helper functions for picking the most common value


def _count(dictionary: dict[T_obj, int], value: T_obj) -> None:
    dictionary[value] += 1


def _count_if_present(dictionary: dict[T_obj, int], value: T_obj | None) -> None:
    if value is not None:
        dictionary[value] += 1


def _common_value(dictionary: dict[T, int]) -> T:
    """Return most commonly occurring key in a dictionary, given the key occurrences.

    The dictionary must not be empty.
    """
    assert dictionary
    return max(dictionary, key=dictionary.__getitem__)


def _common_value_default(dictionary: dict[T, int], default: T) -> T:
    """Return most commonly occurring key in a dictionary, given the key occurrences.

    If the dictionary is empty, the specified default value will be returned instead.
    """
    return default if not dictionary else _common_value(dictionary)


def _common_value_default_none(dictionary: dict[T, int]) -> T | None:
    """Return most commonly occurring key in a dictionary, given the key occurrences.

    If the dictionary is empty, None will be returned instead.
    """
    return None if not dictionary else _common_value(dictionary)


def _common_absolute_track_number(
    abst2_counts: dict[int, int],
    abst1_counts: dict[int, int],
    abst0_counts: dict[int, int],
) -> int | None:
    """Returns the most common absolute track numbers for each track in each channel.

    Call this only after parsing all DIF blocks.
    """
    abst2 = _common_value_default_none(abst2_counts)
    abst1 = _common_value_default_none(abst1_counts)
    abst0 = _common_value_default_none(abst0_counts)
    return (
        None
        if abst2 is None or abst1 is None or abst0 is None
        # remember that abst0 was only 7 bits
        else (abst2 << 15) | (abst1 << 7) | abst0
    )


@dataclass(kw_only=True)
class _BinaryParseState:
    """Stores intermediate state while parsing a binary frame."""

    # These maps count the number of times a value has appeared in the areas where we expect
    # the value to be the same.  For example, header block fields map from the field value
    # to the number of times that value has appeared within all the header blocks of the frame.

    sequence: dict[int, int]
    # Header block

    header_dif_sequence_count: dict[int, int]
    header_track_pitch: dict[block.TrackPitch, int]
    header_pilot_frame: dict[int, int]
    header_application_id_track: dict[block.ApplicationIDTrack, int]
    header_application_id_1: dict[block.ApplicationID1, int]
    header_application_id_2: dict[block.ApplicationID2, int]
    header_application_id_3: dict[block.ApplicationID3, int]

    # Subcode block: ID part

    subcode_index: dict[bool, int]
    subcode_skip: dict[bool, int]
    subcode_picture: dict[bool, int]
    subcode_application_id_track: dict[block.ApplicationIDTrack, int]
    subcode_application_id_3: dict[block.ApplicationID3, int]
    subcode_absolute_track_numbers_2: list[list[dict[int, int]]]
    subcode_absolute_track_numbers_1: list[list[dict[int, int]]]
    subcode_absolute_track_numbers_0: list[list[dict[int, int]]]
    subcode_blank_flag: dict[block.BlankFlag, int]

    # Subcode block: packs part

    subcode_pack_types: list[list[list[int | None]]]
    subcode_title_timecode: dict[pack.TitleTimecode, int]
    subcode_title_binary_group: dict[pack.TitleBinaryGroup, int]
    subcode_vaux_recording_date: dict[pack.VAUXRecordingDate, int]
    subcode_vaux_recording_time: dict[pack.VAUXRecordingTime, int]
    subcode_aaux_recording_date: dict[pack.AAUXRecordingDate, int]
    subcode_aaux_recording_time: dict[pack.AAUXRecordingTime, int]

    # VAUX block

    vaux_pack_types: list[list[list[int | None]]]
    vaux_source: dict[pack.VAUXSource, int]
    vaux_source_control: dict[pack.VAUXSourceControl, int]
    vaux_recording_date: dict[pack.VAUXRecordingDate, int]
    vaux_recording_time: dict[pack.VAUXRecordingTime, int]
    vaux_binary_group: dict[pack.VAUXBinaryGroup, int]
    vaux_camera_consumer_1: dict[pack.CameraConsumer1, int]
    vaux_camera_consumer_2: dict[pack.CameraConsumer2, int]
    vaux_camera_shutter: dict[pack.CameraShutter, int]

    # Audio block: AAUX

    aaux_pack_types: list[list[list[int | None]]]
    aaux_source: list[list[dict[pack.AAUXSource, int]]]
    aaux_source_control: list[list[dict[pack.AAUXSourceControl, int]]]
    aaux_recording_date: list[list[dict[pack.AAUXRecordingDate, int]]]
    aaux_recording_time: list[list[dict[pack.AAUXRecordingTime, int]]]
    aaux_binary_group: list[list[dict[pack.AAUXBinaryGroup, int]]]

    # Audio block: audio data

    audio_blocks: list[list[list[block.Audio | None]]]

    # Video block: video data

    video_blocks: list[list[list[block.Video | None]]]

    @classmethod
    def init_parse_state(cls, file_info: dv_file_info.Info) -> _BinaryParseState:
        """Initialize a new parse state with lists sized to the correct dimensions."""

        return cls(
            sequence=defaultdict(int),
            # Header block
            header_dif_sequence_count=defaultdict(int),
            header_track_pitch=defaultdict(int),
            header_pilot_frame=defaultdict(int),
            header_application_id_track=defaultdict(int),
            header_application_id_1=defaultdict(int),
            header_application_id_2=defaultdict(int),
            header_application_id_3=defaultdict(int),
            # Subcode block: ID part
            subcode_index=defaultdict(int),
            subcode_skip=defaultdict(int),
            subcode_picture=defaultdict(int),
            subcode_application_id_track=defaultdict(int),
            subcode_application_id_3=defaultdict(int),
            subcode_absolute_track_numbers_2=[
                [defaultdict(int) for _ in range(file_info.video_frame_dif_sequence_count)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            subcode_absolute_track_numbers_1=[
                [defaultdict(int) for _ in range(file_info.video_frame_dif_sequence_count)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            subcode_absolute_track_numbers_0=[
                [defaultdict(int) for _ in range(file_info.video_frame_dif_sequence_count)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            subcode_blank_flag=defaultdict(int),
            # Subcode block: packs part
            subcode_pack_types=[
                [[None for _ in range(12)] for _ in range(file_info.video_frame_dif_sequence_count)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            subcode_title_timecode=defaultdict(int),
            subcode_title_binary_group=defaultdict(int),
            subcode_vaux_recording_date=defaultdict(int),
            subcode_vaux_recording_time=defaultdict(int),
            subcode_aaux_recording_date=defaultdict(int),
            subcode_aaux_recording_time=defaultdict(int),
            # VAUX block
            vaux_pack_types=[
                [[None for _ in range(45)] for _ in range(file_info.video_frame_dif_sequence_count)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            vaux_source=defaultdict(int),
            vaux_source_control=defaultdict(int),
            vaux_recording_date=defaultdict(int),
            vaux_recording_time=defaultdict(int),
            vaux_binary_group=defaultdict(int),
            vaux_camera_consumer_1=defaultdict(int),
            vaux_camera_consumer_2=defaultdict(int),
            vaux_camera_shutter=defaultdict(int),
            # Audio block: AAUX block
            aaux_pack_types=[
                [[None for _ in range(9)] for _ in range(file_info.video_frame_dif_sequence_count)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            aaux_source=[
                [defaultdict(int) for _ in range(2)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            aaux_source_control=[
                [defaultdict(int) for _ in range(2)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            aaux_recording_date=[
                [defaultdict(int) for _ in range(2)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            aaux_recording_time=[
                [defaultdict(int) for _ in range(2)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            aaux_binary_group=[
                [defaultdict(int) for _ in range(2)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            # Audio block: audio data
            audio_blocks=[
                [[None for _ in range(9)] for _ in range(file_info.video_frame_dif_sequence_count)]
                for _ in range(file_info.video_frame_channel_count)
            ],
            # Video block: video data
            video_blocks=[
                [
                    [None for _ in range(135)]
                    for _ in range(file_info.video_frame_dif_sequence_count)
                ]
                for _ in range(file_info.video_frame_channel_count)
            ],
        )

    def parse_block(
        self,
        channel: int,
        dif_sequence: int,
        blk: int,  # overall block number within the DIF sequence (not numbered by block type)
        block_bytes: bytes,
        file_info: dv_file_info.Info,
    ) -> None:
        """Stores the block data into the parse state.

        If a value is expected to be the same across multiple blocks, then we count the number of
        occurrences of each unique value in a dictionary to prepare for picking the most common
        value.
        """
        parsed_block = block.parse_binary(block_bytes, file_info)

        # Make sure the block fits in where it should
        if parsed_block.block_id.type != BLOCK_TRANSMISSION_ORDER[blk]:
            raise FrameError(
                "DIF block has an unexpected type: expected "
                f"{du.hex_int(BLOCK_TRANSMISSION_ORDER[blk], 2)} but got "
                f"{du.hex_int(parsed_block.block_id.type, 2)}."
            )
        if parsed_block.block_id.channel != channel:
            raise FrameError(
                "DIF block has an unexpected DIF channel number: expected "
                f"{channel} but got "
                f"{parsed_block.block_id.channel}."
            )
        if parsed_block.block_id.dif_sequence != dif_sequence:
            raise FrameError(
                "DIF block has an unexpected DIF sequence number: expected "
                f"{dif_sequence} but got "
                f"{parsed_block.block_id.dif_sequence}."
            )
        if parsed_block.block_id.dif_block != BLOCK_NUMBER[blk]:
            raise FrameError(
                "DIF block has an unexpected DIF block number: expected "
                f"{BLOCK_NUMBER[blk]} but got "
                f"{parsed_block.block_id.dif_block}."
            )

        # Track the sequence number
        if (
            # These block types always/must have sequence numbers of 0xF.
            parsed_block.block_id.type != block.BlockType.HEADER
            and parsed_block.block_id.type != block.BlockType.SUBCODE
        ):
            _count(self.sequence, parsed_block.block_id.sequence)

        # Track the block data, depending on the type
        if isinstance(parsed_block, block.Header):
            # ===== Header block
            _count(self.header_dif_sequence_count, parsed_block.video_frame_dif_sequence_count)
            _count_if_present(self.header_track_pitch, parsed_block.track_pitch)
            _count_if_present(self.header_pilot_frame, parsed_block.pilot_frame)
            _count_if_present(self.header_application_id_track, parsed_block.application_id_track)
            _count_if_present(self.header_application_id_1, parsed_block.application_id_1)
            _count_if_present(self.header_application_id_2, parsed_block.application_id_2)
            _count_if_present(self.header_application_id_3, parsed_block.application_id_3)
        elif isinstance(parsed_block, block.Subcode):
            # ===== Subcode block: ID part
            for index in parsed_block.index:
                _count_if_present(self.subcode_index, index)
            for skip in parsed_block.skip:
                _count_if_present(self.subcode_skip, skip)
            for picture in parsed_block.picture:
                _count_if_present(self.subcode_picture, picture)
            _count_if_present(self.subcode_application_id_track, parsed_block.application_id_track)
            _count_if_present(self.subcode_application_id_3, parsed_block.application_id_3)
            for atn2 in parsed_block.absolute_track_number_2:
                _count_if_present(
                    self.subcode_absolute_track_numbers_2[channel][dif_sequence], atn2
                )
            for atn1 in parsed_block.absolute_track_number_1:
                _count_if_present(
                    self.subcode_absolute_track_numbers_1[channel][dif_sequence], atn1
                )
            for atn0 in parsed_block.absolute_track_number_0:
                _count_if_present(
                    self.subcode_absolute_track_numbers_0[channel][dif_sequence], atn0
                )
            for blank_flag in parsed_block.blank_flag:
                _count_if_present(self.subcode_blank_flag, blank_flag)

            # ===== Subcode block: packs part
            assert len(parsed_block.pack_types) == 6
            for block_pack_number in range(6):
                overall_pack_number = BLOCK_NUMBER[blk] * 6 + block_pack_number
                self.subcode_pack_types[channel][dif_sequence][overall_pack_number] = (
                    parsed_block.pack_types[block_pack_number]
                )

                p = parsed_block.packs[block_pack_number]
                if isinstance(p, pack.TitleTimecode):
                    _count(self.subcode_title_timecode, p)
                elif isinstance(p, pack.TitleBinaryGroup):
                    _count(self.subcode_title_binary_group, p)
                elif isinstance(p, pack.VAUXRecordingDate):
                    _count(self.subcode_vaux_recording_date, p)
                elif isinstance(p, pack.VAUXRecordingTime):
                    _count(self.subcode_vaux_recording_time, p)
                elif isinstance(p, pack.AAUXRecordingDate):
                    _count(self.subcode_aaux_recording_date, p)
                elif isinstance(p, pack.AAUXRecordingTime):
                    _count(self.subcode_aaux_recording_time, p)
                elif isinstance(p, pack.NoInfo):
                    pass
                else:
                    raise block.BlockError(
                        f"Pack type {du.hex_int(parsed_block.pack_types[block_pack_number], 2)} "
                        "is not currently supported by this program in the subcode block."
                    )
        elif isinstance(parsed_block, block.VAUX):
            # ===== VAUX block
            assert len(parsed_block.pack_types) == 15
            for block_pack_number in range(15):
                overall_pack_number = BLOCK_NUMBER[blk] * 15 + block_pack_number
                self.vaux_pack_types[channel][dif_sequence][overall_pack_number] = (
                    parsed_block.pack_types[block_pack_number]
                )

                p = parsed_block.packs[block_pack_number]
                if isinstance(p, pack.VAUXSource):
                    _count(self.vaux_source, p)
                elif isinstance(p, pack.VAUXSourceControl):
                    _count(self.vaux_source_control, p)
                elif isinstance(p, pack.VAUXRecordingDate):
                    _count(self.vaux_recording_date, p)
                elif isinstance(p, pack.VAUXRecordingTime):
                    _count(self.vaux_recording_time, p)
                elif isinstance(p, pack.VAUXBinaryGroup):
                    _count(self.vaux_binary_group, p)
                elif isinstance(p, pack.CameraConsumer1):
                    _count(self.vaux_camera_consumer_1, p)
                elif isinstance(p, pack.CameraConsumer2):
                    _count(self.vaux_camera_consumer_2, p)
                elif isinstance(p, pack.CameraShutter):
                    _count(self.vaux_camera_shutter, p)
                elif isinstance(p, pack.NoInfo):
                    pass
                else:
                    raise block.BlockError(
                        f"Pack type {du.hex_int(parsed_block.pack_types[block_pack_number], 2)} "
                        "is not currently supported by this program in the VAUX block."
                    )
        elif isinstance(parsed_block, block.Audio):
            # ===== Audio block: AAUX
            audio_block = int(dif_sequence / int(file_info.video_frame_dif_sequence_count / 2))
            overall_pack_number = BLOCK_NUMBER[blk]
            self.aaux_pack_types[channel][dif_sequence][overall_pack_number] = (
                parsed_block.pack_type
            )
            p = parsed_block.pack_data
            if isinstance(p, pack.AAUXSource):
                _count(self.aaux_source[channel][audio_block], p)
            elif isinstance(p, pack.AAUXSourceControl):
                _count(self.aaux_source_control[channel][audio_block], p)
            elif isinstance(p, pack.AAUXRecordingDate):
                _count(self.aaux_recording_date[channel][audio_block], p)
            elif isinstance(p, pack.AAUXRecordingTime):
                _count(self.aaux_recording_time[channel][audio_block], p)
            elif isinstance(p, pack.AAUXBinaryGroup):
                _count(self.aaux_binary_group[channel][audio_block], p)
            elif isinstance(p, pack.NoInfo):
                pass
            else:
                raise block.BlockError(
                    f"Pack type {du.hex_int(parsed_block.pack_type, 2)} is not "
                    "is not currently supported by this program in the audio AAUX block."
                )

            # ===== Audio block: audio data
            self.audio_blocks[channel][dif_sequence][BLOCK_NUMBER[blk]] = parsed_block
        elif isinstance(parsed_block, block.Video):
            # ===== Video block: video data
            self.video_blocks[channel][dif_sequence][BLOCK_NUMBER[blk]] = parsed_block

    def assert_elements_filled(self) -> None:
        """Ensure that all pack type arrays don't have None values in them.

        This should always be the case after all DIF blocks in the frame have been parsed.
        """
        # Check pack types
        assert len(self.subcode_pack_types) == len(self.vaux_pack_types)
        assert len(self.subcode_pack_types) == len(self.aaux_pack_types)
        # Also check audio/video data
        assert len(self.subcode_pack_types) == len(self.audio_blocks)
        assert len(self.subcode_pack_types) == len(self.video_blocks)
        for chn in range(len(self.subcode_pack_types)):
            assert len(self.subcode_pack_types[chn]) == len(self.vaux_pack_types[chn])
            assert len(self.subcode_pack_types[chn]) == len(self.aaux_pack_types[chn])
            assert len(self.subcode_pack_types[chn]) == len(self.audio_blocks[chn])
            assert len(self.subcode_pack_types[chn]) == len(self.video_blocks[chn])
            for seq in range(len(self.subcode_pack_types[chn])):
                assert not any(p is None for p in self.subcode_pack_types[chn][seq])
                assert not any(p is None for p in self.vaux_pack_types[chn][seq])
                assert not any(p is None for p in self.aaux_pack_types[chn][seq])
                assert not any(ab is None for ab in self.audio_blocks[chn][seq])
                assert not any(vb is None for vb in self.video_blocks[chn][seq])

    @staticmethod
    def _must_has_audio_errors(
        blk: block.Audio | None,
        file_info: dv_file_info.Info,
        source_pack: pack.AAUXSource | None,
    ) -> bool:
        assert blk is not None
        if (
            source_pack is None
            or source_pack.audio_samples_per_frame is None
            or source_pack.quantization is None
        ):
            # If the audio block has no valid AAUX source packs at all, then assume it's an error
            return True
        return blk.has_audio_errors(
            file_info, source_pack.audio_samples_per_frame, source_pack.quantization
        )

    def calc_audio_errors(
        self, file_info: dv_file_info.Info
    ) -> tuple[list[list[list[bool]]], list[list[float]]]:
        sequences_per_audio_block = int(file_info.video_frame_dif_sequence_count / 2)
        # indexed by DIF channel, audio block number
        aaux_source: list[list[pack.AAUXSource | None]] = [
            [
                _common_value_default_none(self.aaux_source[channel][audio_block])
                for audio_block in range(len(self.aaux_source[channel]))
            ]
            for channel in range(len(self.aaux_source))
        ]
        # indexed by DIF channel, sequence number
        aaux_source_by_seq: list[list[pack.AAUXSource | None]] = [
            [
                aaux_source[channel][int(sequence / sequences_per_audio_block)]
                for sequence in range(file_info.video_frame_dif_sequence_count)
            ]
            for channel in range(len(aaux_source))
        ]
        # return error status, indexed by DIF channel, sequence, audio DIF block
        audio_errors = [
            [
                [
                    self._must_has_audio_errors(
                        blk, file_info, cast(pack.AAUXSource, aaux_source_by_seq[channel][sequence])
                    )
                    for blk in self.audio_blocks[channel][sequence]
                ]
                for sequence in range(len(self.audio_blocks[channel]))
            ]
            for channel in range(len(self.audio_blocks))
        ]
        # flattened audio errors by audio block: indexed by DIF channel, audio block number,
        # flattened DIF block errors
        flattened_audio_errors: list[list[list[bool]]] = [
            [
                [
                    block_err
                    for sequence_errors in audio_errors[channel][
                        (audio_block * sequences_per_audio_block) : (
                            audio_block * sequences_per_audio_block + sequences_per_audio_block
                        )
                    ]
                    for block_err in sequence_errors
                ]
                for audio_block in range(2)
            ]
            for channel in range(len(audio_errors))
        ]
        audio_data_error_summary = [
            [sum(audio_block) / len(audio_block) for audio_block in channel]
            for channel in flattened_audio_errors
        ]
        return audio_errors, audio_data_error_summary

    @staticmethod
    def _must_has_video_errors(blk: block.Video | None) -> bool:
        assert blk is not None
        return blk.has_video_errors()

    def calc_video_errors(self) -> tuple[list[list[list[bool]]], float]:
        video_errors = [
            [
                [self._must_has_video_errors(blk) for blk in sequence_video]
                for sequence_video in channel_video
            ]
            for channel_video in self.video_blocks
        ]
        flattened_video_errors = [
            block_err
            for channel_errors in video_errors
            for sequence_errors in channel_errors
            for block_err in sequence_errors
        ]
        video_data_error_summary = sum(flattened_video_errors) / len(flattened_video_errors)
        return video_errors, video_data_error_summary
