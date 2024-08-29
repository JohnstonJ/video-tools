from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, cast

import video_tools.dv.file.info as dv_file_info
import video_tools.dv.pack as pack

from .base import Block, BlockError, BlockID, BlockType
from .header import ApplicationID3, ApplicationIDTrack


# Blank flag: determines whether a discontinuity in the absolute track number exists prior to the
# current track.
# IEC 61834-2:1998 Section 8.4.4 - Absolute track number - Numbering of absolute track number
class BlankFlag(IntEnum):
    DISCONTINUOUS = 0x0
    CONTINUOUS = 0x1


# DIF subcode block
# Standards on how subcode data is packaged in the digital interface:
#  - IEC 61834-2:1998 Section 11.4.2 - Data part - Subcode section
#  - IEC 61834-2:1998 Figure 68 - Data in the subcode section
#  - IEC 61834-2:1998 Table 40 - DIF blocks and subcode sync blocks
#  - IEC 61834-2:1998 Table B.4 - Method of transmitting and recording data of subcode DIF block
#  - SMPTE 306M-2002 Section 11.2.2.2 - Subcode section
# Standards on the formatting of the subcode blocks themselves:
#  - IEC 61834-2:1998 Section 3.5 - Subcode sector
#  - IEC 61834-2:1998 Figure 12 - Structure of sync blocks in subcode sector
#  - IEC 61834-2:1998 Section 8 - Subcode signal processing
#  - IEC 61834-2:1998 Section 9.3 - Main area and optional area
#  - SMPTE 306M-2002 Section 6.5 - Subcode sector
#  - SMPTE 306M-2002 Section 9 - Subcode processing
# Important notes:
#  - Each tape track physically holds 12 subcode-containing sync blocks.
#  - Each sync block contains 3 ID bytes and 5 bytes for a single pack, which are described in more
#    detail within the class.
#  - The 12 sync blocks are distributed evenly across 2 DIF subcode blocks within a single DIF
#    sequence/track.  Since this class is for a single DIF block, it holds only 6 sync blocks.
#  - All 6 8-byte sync blocks within a DIF block are subject to tape read errors, such as:
#     - Both sync block ID bytes and pack bytes are missing (all 8 bytes are 0xFF).  Experimentally
#       observed in practice.
#     - Sync block ID bytes may be present, but the 5 pack bytes are 0xFF (NO INFO pack).
#       Experimentally observed in practice.
#     - Pack may be present, but sync block ID bytes are absent/invalid.  Experimentally observed in
#       practice.
#     - A slight amount of data from adjacent video frames could spill over into this one.  For
#       example, title timecode packs might be carried over from the previous frame.  Alternatively,
#       sync block ID bytes could also spill over (e.g. absolute track number from a nearby frame
#       is used).  Both of these examples have been experimentally observed in practice.
#     - The sync block ID bytes and pack bytes are covered by independent error correcting codes.
#       We will therefore most likely not see actual garbage data, but rather just dropout
#       bytes (0xFF) or (valid but misaligned) data from adjacent tape tracks / video frames.
#       HOWEVER: IEC 61834-2:1998 Section 9.2.4 - Error expression, states that single bytes within
#       a pack may be individually replaced with 0xFF, rather than replacing the entire pack with
#       NO INFO.  So.... don't put too much trust in error correction?
#  - In summary: the most robust mindset for correcting errors is if one assumes that any byte could
#    be missing/0xFF, from an adjacent frame, or outright wrong.  In practice, a dropped frame is
#    experimentally observed to have a 100% 0xFF DIF block (apart from the DIF block ID).
#  - The trailing reserved bytes after the sync blocks are not from tape, so will always be 0xFF.
@dataclass(frozen=True, kw_only=True)
class Subcode(Block):
    # ======================== ID PART ========================
    # List of more specific standards sections that pertain to the ID part of a subcode sync block:
    #  - IEC 61834-2:1998 Section 3.5.3 - ID part (Subcode sector)
    #  - IEC 61834-2:1998 Figure 13 - ID data in subcode sector
    #  - IEC 61834-2:1998 Section 8.4 - ID data (Subcode signal processing)
    #  - IEC 61834-2:1998 Figure 42 - Structure of ID data
    #  - SMPTE 306M-2002 Section 6.5.3.2 - ID (Subcode sync block)
    # Important notes:
    #  - First 3 bytes of an 8-byte sync block are [ID0, ID1, ID parity]
    #  - The ID parity byte is always 0xFF on the digital interface.
    #  - ID0 and ID1 are described in detail in the above-referenced sections and figures.
    #    IEC 61834-2 Figure 42 is one of the best references.
    #  - If the sync block number is 0xF, that means "no information", which presumably should
    #    mean that the entire sync block should be discarded (or at least the ID part).  However,
    #    I've experimentally seen where the sync block number is not 0xF, and yet was the _only_
    #    nibble out of the _entire_ sync block that was not 0xF.  So a value other than 0xF doesn't
    #    prove validity of the rest of the data.  (i.e. sync block of "FFFA FF FF FFFFFFFF")

    # Note that many values are repeated throughout the DIF sequence/track and the video frame.
    # For example, the area 3 application IDs, and index/skip bits are repeated multiple times,
    # even though they're expected to be the same.  However, they might not be, in the case of read
    # errors.  All copies of the value are returned so they can be analyzed / corrected for error.

    # Tag bits, as defined in IEC 61834-2:1998 Section 8.4.3 - TAG ID
    #
    # These bits are used for searching for specific locations marked by the end user on tape while
    # fast-forwarding.
    #
    # Each value is supposed to be the same throughout the video frame, but might not be if there
    # were read errors.  In practice, these tag bits may be marked consistently throughout several
    # seconds of frames so that they can be reliably identified while fast-forwarding.
    #
    # Each tag value has 5 elements in DIF block 0, and 4 elements in DIF block 1.  A value of None
    # means that another part of the ID block had a read error that leads us to not trust this bit.

    # Indicates a location of interest marked by the user to search for on the tape, similar to
    # the "index" search feature on analog VHS tapes / VCRs.
    index: list[bool | None]  # True means "mark"
    # Indicates the start of a range of frames that the user would like to skip.  The end frame
    # is delimited by an index marker.  The tape deck can then automatically fast-forward the
    # section (e.g. a segment of TV commercials).
    skip: list[bool | None]  # True means "mark"
    # Indicates that the frame has been tagged as a still picture, instead of a moving image.
    picture: list[bool | None]  # True means "mark"

    # The application IDs from the DIF header are reproduced here.  The reliability of the read
    # data may be lower than the values in the DIF header.  The values should be the same throughout
    # the entire frame, and identical to the corresponding values in the DIF header.
    #
    # None means a read error or dropout.  The application ID for area 3 should be present in both
    # DIF subcode blocks.  The track application ID is only physically present in DIF subcode
    # block 1, so it's always None in DIF subcode block 0.  Otherwise, a value of None means there
    # was a read error or dropout.
    application_id_track: ApplicationIDTrack | None
    application_id_3: ApplicationID3 | None

    # Absolute track number: every tape track is assigned a number from the start of the tape.
    #  - IEC 61834-2:1998 Section 8.4.4 - Absolute track number
    #  - IEC 61834-2:1998 Figure 43 - Structure of the absolute track number
    #  - IEC 61834-2:1998 Figure 44 - Recommendation for the recording start position of a tape
    #  - IEC 61834-2:1998 Figure 45 - Numbering of the absolute track number for invalid tracks
    #  - IEC 61834-1:1998 Amendment 1 Section A.3 - Absolute track numbering (for LP mode)
    #  - IEC 61834-1:1998 Amendment 1 Figure A.2 - Absolute track numbering for LP mode
    # Important notes:
    #  - The values must be the same within a single DIF sequence, which is a single tape track.
    #  - Standard play: the value must increment by 1 for every DIF sequence/track.
    #  - Long play: even values are repeated once (e.g. tracks numbered 0, 0, 1, 2, 2, 3, 4, 4)
    # To help with later error recovery, the individual bytes of each copy of the ATN are kept here.
    # A value of None means that there was a strong reason to believe the bits were invalid.
    absolute_track_number_2: list[int | None]  # most significant byte; 2 per DIF block
    absolute_track_number_1: list[int | None]  # middle byte; 2 per DIF block
    # least significant byte, shifted to the right by 1 to remove BF flag
    absolute_track_number_0: list[int | None]  # 2 per DIF block
    blank_flag: list[BlankFlag | None]  # 2 per DIF block

    # ======================== DATA/PACK PART ========================
    # List of more specific standards sections that pertain to the pack part:
    #  - IEC 61834-2:1998 Section 8.5 - Subcode data
    #  - IEC 61834-2:1998 Section 9 - System data
    #  - IEC 61834-4:1998 - entire standard
    #  - SMPTE 306M-2002 Section 9 - Subcode processing
    # Important notes:
    #  - The various standards prescribe various packs that are required to go in certain positions,
    #    and other areas that are reserved or optional.  In practice, we will be flexible when
    #    parsing and writing, and allow any pack to appear in any position.

    # Parsed pack; will be None if there is a pack parse error due to tape errors.
    packs: list[pack.Pack | None]  # 6 per DIF block; None if there is a parse error
    # List of pack type header values: this is purely informational when reading, and is not used
    # at all when writing subcode blocks back out to binary.  It's useful to know what pack type
    # failed to be read if the above packs[n] element is None.
    pack_types: list[int]  # 6 per DIF block

    def validate(self, file_info: dv_file_info.Info) -> str | None:
        if self.block_id.dif_block < 0 or self.block_id.dif_block > 1:
            return "Unexpected number of DIF blocks in DIF sequence; expected 2."

        # Check array lengths; these are simple assertions since the end-user should never be able
        # to trigger these and need pretty validation messages.
        tag_count = 5 if self.block_id.dif_block == 0 else 4
        assert len(self.index) == tag_count
        assert len(self.skip) == tag_count
        assert len(self.picture) == tag_count
        assert len(self.absolute_track_number_0) == 2
        assert len(self.absolute_track_number_1) == 2
        assert len(self.absolute_track_number_2) == 2
        assert len(self.blank_flag) == 2
        assert len(self.packs) == 6
        assert len(self.pack_types) == 6

        # Each ID part should be completely valid, or completely missing
        for dif_sync_block_number in range(6):
            syb_number = self.block_id.dif_block * 6 + dif_sync_block_number
            id_part_uneven = f"All parts of sync block {syb_number} must be all present or absent."

            if dif_sync_block_number == 0:
                id_part_missing = self.application_id_3 is None
            elif self.block_id.dif_block == 1 and dif_sync_block_number == 5:
                id_part_missing = self.application_id_track is None
            else:
                tag_index = dif_sync_block_number - 1
                id_part_missing = self.index[tag_index] is None
                if (self.skip[tag_index] is None) != id_part_missing or (
                    self.picture[tag_index] is None
                ) != id_part_missing:
                    return id_part_uneven

            abst_index = int(dif_sync_block_number / 3)
            match dif_sync_block_number % 3:  # which position in a given/single ABST?
                case 0:
                    abst = self.absolute_track_number_0[abst_index]
                    if (abst is None) != id_part_missing or (
                        (self.blank_flag[abst_index] is None) != id_part_missing
                    ):
                        return id_part_uneven
                    assert abst is None or (abst >= 0 and abst <= 0x7F)
                case 1:
                    abst = self.absolute_track_number_1[abst_index]
                    if (abst is None) != id_part_missing:
                        return id_part_uneven
                    assert abst is None or (abst >= 0 and abst <= 0xFF)
                case 2:
                    abst = self.absolute_track_number_2[abst_index]
                    if (abst is None) != id_part_missing:
                        return id_part_uneven
                    assert abst is None or (abst >= 0 and abst <= 0xFF)

        return None

    # Functions for going to/from binary blocks

    type: ClassVar[BlockType] = BlockType.SUBCODE

    @classmethod
    def _do_parse_binary(
        cls, block_bytes: bytes, block_id: BlockID, file_info: dv_file_info.Info
    ) -> Subcode:
        bin = _BinaryFields.from_buffer_copy(block_bytes[3:])

        # allocate subcode fields that we will parse into
        tag_count = 5 if block_id.dif_block == 0 else 4
        index: list[bool | None] = [None] * tag_count
        skip: list[bool | None] = [None] * tag_count
        picture: list[bool | None] = [None] * tag_count
        application_id_track = None
        application_id_3 = None
        absolute_track_number_2: list[int | None] = [None] * 2
        absolute_track_number_1: list[int | None] = [None] * 2
        absolute_track_number_0: list[int | None] = [None] * 2
        blank_flag: list[BlankFlag | None] = [None] * 2
        packs: list[pack.Pack | None] = [None] * 6
        pack_types = [int(pack.Type.NO_INFO)] * 6

        # This is the first half of _each channel_.
        expected_first_half_id = (
            1 if block_id.dif_sequence < file_info.video_frame_dif_sequence_count / 2 else 0
        )

        # Process ID parts
        for dif_sync_block_number in range(6):
            expected_syb = block_id.dif_block * 6 + dif_sync_block_number
            id_part = bin.sync_blocks[dif_sync_block_number].id

            # Do some validation of the ID part to see if it's likely to be obviously wrong

            # If the identifying parts of the sync block are easily shown to be wrong, then the
            # rest of the ID part is probably wrong.  The pack may or may not be wrong, but
            # the pack will probably have a NO INFO pack header anyway, and packs have their own
            # validation.  So this logic is just used to exclude ID parts from processing.
            if (
                id_part.id0.with_tag.fr != expected_first_half_id
                or id_part.id1.with_bf.syb != expected_syb
            ):
                continue
            # Application IDs, when expected to be present, are another way to exclude bad ID parts
            if dif_sync_block_number == 0 and id_part.id0.with_application_id.application_id == 0x7:
                continue
            if (
                block_id.dif_block == 1
                and dif_sync_block_number == 5
                and id_part.id0.with_application_id.application_id == 0x7
            ):
                continue

            # Parity byte is ALWAYS 0xFF on the digital interface
            if id_part.parity != 0xFF:
                raise BlockError(
                    f"Sync block parity byte is not 0xFF for sync block {expected_syb}."
                )

            # Now, pull out the various bits of the ID part

            # First 4 bits of ID part may hold tag ID or application ID, depending on block number
            if dif_sync_block_number == 0:
                application_id_3 = ApplicationID3(id_part.id0.with_application_id.application_id)
            elif block_id.dif_block == 1 and dif_sync_block_number == 5:
                application_id_track = ApplicationIDTrack(
                    id_part.id0.with_application_id.application_id
                )
            else:
                tag_index = dif_sync_block_number - 1
                index[tag_index] = True if id_part.id0.with_tag.index == 0 else False
                skip[tag_index] = True if id_part.id0.with_tag.skip == 0 else False
                picture[tag_index] = True if id_part.id0.with_tag.pp == 0 else False

            # The rest is a repeating absolute track number
            abst_index = int(dif_sync_block_number / 3)
            match dif_sync_block_number % 3:  # which position in a given/single ABST?
                case 0:
                    abst_upper = id_part.id0.with_tag.abst
                    abst_lower = id_part.id1.with_bf.abst
                    absolute_track_number_0[abst_index] = (abst_upper << 3) | abst_lower
                    blank_flag[abst_index] = BlankFlag(id_part.id1.with_bf.bf)
                case 1:
                    abst_upper = id_part.id0.with_tag.abst
                    abst_lower = id_part.id1.without_bf.abst
                    absolute_track_number_1[abst_index] = (abst_upper << 4) | abst_lower
                case 2:
                    abst_upper = id_part.id0.with_tag.abst
                    abst_lower = id_part.id1.without_bf.abst
                    absolute_track_number_2[abst_index] = (abst_upper << 4) | abst_lower

        # Now, read and parse the packs
        for dif_sync_block_number in range(6):
            packs[dif_sync_block_number] = pack.parse_binary(
                bin.sync_blocks[dif_sync_block_number].data, file_info.system
            )
            pack_types[dif_sync_block_number] = bin.sync_blocks[dif_sync_block_number].data[0]

        # Quick check on the trailing reserved bits, which don't come from tape
        if any(r != 0xFF for r in bin.reserved):
            raise BlockError("Reserved bits in DIF header block are unexpectedly in use.")

        return cls(
            block_id=block_id,
            index=index,
            skip=skip,
            picture=picture,
            application_id_track=application_id_track,
            application_id_3=application_id_3,
            absolute_track_number_2=absolute_track_number_2,
            absolute_track_number_1=absolute_track_number_1,
            absolute_track_number_0=absolute_track_number_0,
            blank_flag=blank_flag,
            packs=packs,
            pack_types=pack_types,
        )

    def _do_to_binary(self, file_info: dv_file_info.Info) -> bytes:
        # Process ID parts
        id_parts: list[_IDPart] = []
        for dif_sync_block_number in range(6):
            id_block_valid = True

            # First 4 bits of ID part may hold tag ID or application ID, depending on block number
            application_id = None
            index = None
            skip = None
            pp = None
            if dif_sync_block_number == 0:
                application_id = (
                    int(self.application_id_3) if self.application_id_3 is not None else 0x7
                )
                id_block_valid = id_block_valid and self.application_id_3 is not None
            elif self.block_id.dif_block == 1 and dif_sync_block_number == 5:
                application_id = (
                    int(self.application_id_track) if self.application_id_track is not None else 0x7
                )
                id_block_valid = id_block_valid and self.application_id_track is not None
            else:
                tag_index = dif_sync_block_number - 1
                index = 1 if not self.index[tag_index] else 0
                skip = 1 if not self.skip[tag_index] else 0
                pp = 1 if not self.picture[tag_index] else 0
                id_block_valid = (
                    id_block_valid
                    and self.index[tag_index] is not None
                    and self.skip[tag_index] is not None
                    and self.picture[tag_index] is not None
                )

            # Absolute track number
            abst_index = int(dif_sync_block_number / 3)
            bf = None
            match dif_sync_block_number % 3:  # which position in a given/single ABST?
                case 0:
                    atn = self.absolute_track_number_0[abst_index]
                    bf_enum = self.blank_flag[abst_index]
                    abst = atn if atn is not None else 0x7F
                    abst_upper = abst >> 3
                    abst_lower = abst & 0x7
                    bf = int(bf_enum) if bf_enum is not None else 0x1
                    id_block_valid = id_block_valid and bf_enum is not None and atn is not None
                case 1:
                    atn = self.absolute_track_number_1[abst_index]
                    abst = atn if atn is not None else 0xFF
                    abst_upper = abst >> 4
                    abst_lower = abst & 0xF
                    id_block_valid = id_block_valid and atn is not None
                case 2:
                    atn = self.absolute_track_number_2[abst_index]
                    abst = atn if atn is not None else 0xFF
                    abst_upper = abst >> 4
                    abst_lower = abst & 0xF
                    id_block_valid = id_block_valid and atn is not None

            # Identifying bits are only set if the ID part is fully valid (i.e. nothing was None).
            #
            # FR bit: This identifies the first half of sequences _within each channel_.
            fr = (
                (
                    1
                    if self.block_id.dif_sequence < file_info.video_frame_dif_sequence_count / 2
                    else 0
                )
                if id_block_valid
                else 0x1
            )
            syb = self.block_id.dif_block * 6 + dif_sync_block_number if id_block_valid else 0xF

            id_part = _IDPart(
                id0=(
                    _ID0Part(
                        with_tag=_ID0PartWithTag(
                            fr=fr,
                            index=index,
                            skip=skip,
                            pp=pp,
                            abst=abst_upper,
                        )
                    )
                    if index is not None
                    else _ID0Part(
                        with_application_id=_ID0PartWithApplicationID(
                            fr=fr,
                            application_id=application_id,
                            abst=abst_upper,
                        )
                    )
                ),
                id1=(
                    _ID1Part(
                        with_bf=_ID1PartWithBF(
                            abst=abst_lower,
                            bf=bf,
                            syb=syb,
                        )
                    )
                    if bf is not None
                    else _ID1Part(
                        without_bf=_ID1PartWithoutBF(
                            abst=abst_lower,
                            syb=syb,
                        )
                    )
                ),
                parity=0xFF,
            )
            id_parts.append(id_part)

        # Build final output
        bin = _BinaryFields(
            sync_blocks=(_SyncBlock * 6)(
                *[
                    _SyncBlock(
                        id=id_parts[dif_sync_block_number],
                        data=(ctypes.c_uint8 * 5)(
                            *(
                                cast(pack.Pack, self.packs[dif_sync_block_number]).to_binary(
                                    file_info.system
                                )
                                if self.packs[dif_sync_block_number] is not None
                                # Send a NO INFO pack if we are missing a pack (e.g. from a previous
                                # read error).
                                else pack.NoInfo().to_binary(file_info.system)
                            )
                        ),
                    )
                    for dif_sync_block_number in range(6)
                ]
            ),
            reserved=(ctypes.c_uint8 * 29)(*[0xFF] * 29),
        )
        return bytes([*self.block_id.to_binary(file_info), *bytes(bin)])


class _ID0PartWithTag(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("fr", ctypes.c_uint8, 1),  # first half ID: 1 for first half, 0 for second
        ("index", ctypes.c_uint8, 1),
        ("skip", ctypes.c_uint8, 1),
        ("pp", ctypes.c_uint8, 1),
        ("abst", ctypes.c_uint8, 4),
    ]


class _ID0PartWithApplicationID(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("fr", ctypes.c_uint8, 1),  # first half ID: 1 for first half, 0 for second
        ("application_id", ctypes.c_uint8, 3),
        ("abst", ctypes.c_uint8, 4),
    ]


class _ID0Part(ctypes.BigEndianUnion):
    _pack_ = 1
    _fields_: ClassVar = [
        ("with_tag", _ID0PartWithTag),
        ("with_application_id", _ID0PartWithApplicationID),
    ]


class _ID1PartWithBF(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("abst", ctypes.c_uint8, 3),
        ("bf", ctypes.c_uint8, 1),
        ("syb", ctypes.c_uint8, 4),
    ]


class _ID1PartWithoutBF(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("abst", ctypes.c_uint8, 4),
        ("syb", ctypes.c_uint8, 4),
    ]


class _ID1Part(ctypes.BigEndianUnion):
    _pack_ = 1
    _fields_: ClassVar = [
        ("with_bf", _ID1PartWithBF),
        ("without_bf", _ID1PartWithoutBF),
    ]


class _IDPart(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("id0", _ID0Part),
        ("id1", _ID1Part),
        ("parity", ctypes.c_uint8, 8),  # always 0xFF over digital interface
    ]


class _SyncBlock(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("id", _IDPart),
        ("data", ctypes.c_uint8 * 5),
    ]


class _BinaryFields(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_: ClassVar = [
        ("sync_blocks", _SyncBlock * 6),
        ("reserved", ctypes.c_uint8 * 29),
    ]
