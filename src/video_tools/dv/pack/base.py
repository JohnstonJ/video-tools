"""Base classes for defining DIF packs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import IntEnum
from typing import Any, ClassVar, NamedTuple, cast

import video_tools.dv.file.info as dv_file_info


class ValidationError(ValueError):
    pass


# Pack types
# IEC 61834-4:1998
class Type(IntEnum):
    # SMPTE 306M-2002 Section 9.2.1 Time code pack (TC)
    # IEC 61834-4:1998 4.4 Time Code (TITLE)
    TITLE_TIMECODE = 0x13

    # SMPTE 306M-2002 Section 9.2.2 Binary group pack (BG)
    # IEC 61834-4:1998 4.5 Binary Group
    TITLE_BINARY_GROUP = 0x14

    # IEC 61834-4:1998 8.1 Source (AAUX)
    AAUX_SOURCE = 0x50

    # IEC 61834-4:1998 8.3 Rec Date (AAUX)
    AAUX_RECORDING_DATE = 0x52

    # IEC 61834-4:1998 8.4 Rec Time (AAUX)
    AAUX_RECORDING_TIME = 0x53

    # IEC 61834-4:1998 8.5 Binary Group (AAUX)
    AAUX_BINARY_GROUP = 0x54

    # IEC 61834-4:1998 9.1 Source (VAUX)
    VAUX_SOURCE = 0x60

    # IEC 61834-4:1998 9.2 Source control (VAUX)
    VAUX_SOURCE_CONTROL = 0x61

    # IEC 61834-4:1998 9.3 Rec Date (Recording date) (VAUX)
    VAUX_RECORDING_DATE = 0x62

    # IEC 61834-4:1998 9.4 Rec Time (VAUX)
    VAUX_RECORDING_TIME = 0x63

    # IEC 61834-4:1998 9.5 Binary Group (VAUX)
    VAUX_BINARY_GROUP = 0x64

    # IEC 61834-4:1998 12.16 No Info: No information (SOFT MODE)
    # Also, very commonly a dropout - especially in the subcode DIF block
    NO_INFO = 0xFF


# NOTE:  Pack fields are often ultimately all required to be valid, but we allow them to
# be missing during intermediate transformations / in CSV files.  Validity checks are done
# when serializing to/from pack binary blobs.


CSVFieldMap = dict[str | None, type[NamedTuple]]


@dataclass(frozen=True, kw_only=True)
class Pack(ABC):
    @abstractmethod
    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        """Indicate whether the contents of the pack are fully valid.

        A fully valid pack can be safely written to a binary DV file.  When reading a binary
        DV file, this function is used to throw out corrupted packs.

        The return value contains a description of the validation failure.  If the pack passes
        validation, then None is returned.
        """
        pass

    # Abstract functions for converting subsets of pack values to/from strings suitable for use
    # in a CSV file or other configuration files.  Pack value subsets are a NamedTuple whose
    # field values must match the field values defined in the main dataclass.

    # Dict of text field names used when saving the pack to a CSV file.
    # The dictionary values are NamedTuple types for the subset of pack values that go into it.
    #
    # Special: if the text field name is None, then it's considered the default/main value for the
    # pack.  This affects prefixes that are prepended to the final CSV field name:
    #     field name of None --> sc_smpte_timecode
    #     field name of 'blank_flag' --> sc_smpte_timecode_blank_flag
    text_fields: ClassVar[CSVFieldMap]

    @classmethod
    @abstractmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        """Parse the value for a CSV text field name into a tuple of dataclass field values.

        The returned keys must match with keyword arguments in the initializer.
        """
        pass

    @classmethod
    @abstractmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        """Convert a subset of the pack field values to a single CSV text field value.

        The value_subset is what is returned by value_subset_for_text_field."""
        pass

    def value_subset_for_text_field(self, text_field: str | None) -> NamedTuple:
        """Returns a subset of dataclass field values that are used by the given text_field.

        The returned keys must match with keyword arguments in the initializer."""
        typ = self.text_fields[text_field]
        full_dict = asdict(self)
        subset_dict = {field_name: full_dict[field_name] for field_name in typ._fields}
        # For some reason, I can't figure out how to get mypy to think I'm invoking the type
        # initializer, rather than the NamedType builtin function itself...
        return cast(NamedTuple, typ(**subset_dict))  # type: ignore[call-overload]

    # Functions for converting all pack values to/from multiple CSV file fields.

    @classmethod
    def parse_text_values(cls, text_field_values: dict[str | None, str]) -> Pack:
        """Create a new instance of the pack by parsing text values.

        Any missing field values will be assumed to have a value of the empty string.
        """
        parsed_values: dict[str, Any] = {}
        for text_field, text_value in text_field_values.items():
            parsed_values |= cls.parse_text_value(text_field, text_value)._asdict()
        return cls(**parsed_values)

    def to_text_values(self) -> dict[str | None, str]:
        """Convert the pack field values to text fields."""
        result = {}
        for text_field in self.text_fields.keys():
            result[text_field] = self.to_text_value(
                text_field, self.value_subset_for_text_field(text_field)
            )
        return result

    # Functions for going to/from binary packs

    # Binary byte value for the pack type header.
    pack_type: ClassVar[Type]

    @classmethod
    @abstractmethod
    def _do_parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> Pack | None:
        """The derived class should parse the bytes into a new Pack object.

        It does not need to assert the length of pack_bytes or assert that the pack type is indeed
        correct.  It also does not need to call pack.validate() and return None if it's invalid.
        The main parse_binary function does those common tasks for you.
        """

    @classmethod
    def parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> Pack | None:
        """Create a new instance of the pack by parsing a binary blob from a DV file.

        The input byte array is expected to be 5 bytes: pack type byte followed by 4 data bytes.
        """
        assert len(pack_bytes) == 5
        assert pack_bytes[0] == cls.pack_type
        pack = cls._do_parse_binary(pack_bytes, system)
        return pack if pack is not None and pack.validate(system) is None else None

    @abstractmethod
    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        """Convert this pack to binary; the pack can be assumed to be valid."""
        pass

    def to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        """Convert this pack to the 5 byte binary format."""
        validation_message = self.validate(system)
        if validation_message is not None:
            raise ValidationError(validation_message)
        b = self._do_to_binary(system)
        assert len(b) == 5
        assert b[0] == self.pack_type
        return b
