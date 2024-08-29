"""Model classes for working with raw DIF data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, NamedTuple

import video_tools.dv.data_util as du
import video_tools.dv.file_info as dv_file_info

from .base import CSVFieldMap, Pack, PackType, PackValidationError


# Generic SMPTE binary group base class: several pack types reuse the same structure.
# See the derived classes for references to the standards.
@dataclass(frozen=True, kw_only=True)
class GenericBinaryGroup(Pack):
    # this will always be 4 bytes
    value: bytes | None = None

    class MainFields(NamedTuple):
        value: bytes | None  # Formats as 8 hex digits

    text_fields: ClassVar[CSVFieldMap] = {None: MainFields}

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if self.value is None:
            return "A binary group value was not provided."
        if len(self.value) != 4:
            return (
                "The binary group has the wrong length: expected 4 bytes "
                f"but got {len(self.value)}."
            )
        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        assert text_field is None
        return cls.MainFields(
            value=bytes.fromhex(text_value.removeprefix("0x")) if text_value else None
        )

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        assert text_field is None
        assert isinstance(value_subset, cls.MainFields)
        return du.hex_bytes(value_subset.value) if value_subset.value is not None else ""

    @classmethod
    def _do_parse_binary(
        cls, pack_bytes: bytes, system: dv_file_info.DVSystem
    ) -> GenericBinaryGroup | None:
        return cls(value=bytes(pack_bytes[1:]))

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.value is not None  # assertion repeated from validate() to keep mypy happy
        return bytes(
            [
                self.pack_type,
                self.value[0],
                self.value[1],
                self.value[2],
                self.value[3],
            ]
        )


# Title binary group
# SMPTE 306M-2002 Section 9.2.2 Binary group pack (BG)
# IEC 61834-4:1998 4.5 Binary Group (TITLE)
# Also see SMPTE 12M
@dataclass(frozen=True, kw_only=True)
class TitleBinaryGroup(GenericBinaryGroup):
    pack_type = PackType.TITLE_BINARY_GROUP


# AAUX binary group
# IEC 61834-4:1998 8.5 Binary Group (AAUX)
@dataclass(frozen=True, kw_only=True)
class AAUXBinaryGroup(GenericBinaryGroup):
    pack_type = PackType.AAUX_BINARY_GROUP


# VAUX binary group
# IEC 61834-4:1998 9.5 Binary Group (VAUX)
@dataclass(frozen=True, kw_only=True)
class VAUXBinaryGroup(GenericBinaryGroup):
    pack_type = PackType.VAUX_BINARY_GROUP


# No Info block
# IEC 61834-4:1998 12.16 No Info: No information (SOFT MODE)
# Also, very commonly a dropout - especially in the subcode DIF block
@dataclass(frozen=True, kw_only=True)
class NoInfo(Pack):
    text_fields: ClassVar[CSVFieldMap] = {}

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        assert False

    pack_type = PackType.NO_INFO

    @classmethod
    def _do_parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> NoInfo | None:
        # The standard says that pack_bytes will always be 0xFFFFFFFFFF.  In practice, you'll also
        # "get" this pack as a result of dropouts from other packs: if the leading pack header is
        # lost and becomes 0xFF (this pack type), but the rest of the pack is not lost, then we'd
        # see other non-0xFF bytes here.  Unfortunately, in such a scenario, since the pack header
        # was lost, we don't know what pack that data is supposed to go with.  So we'll just let
        # this pack discard those bytes as it's probably not worth trying to preserve them.
        return cls()

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        return bytes([self.pack_type, 0xFF, 0xFF, 0xFF, 0xFF])


# Unknown pack: holds the bytes for any pack type we don't know about in a particular DIF block.
# These are not aggregated or written to the CSV, since it isn't known if it's meaningful to do
# that.  They do show up when parsing DIF blocks so that we can retain the bytes.
@dataclass(frozen=True, kw_only=True)
class Unknown(Pack):
    # this will always be 5 bytes: includes the pack header
    value: bytes | None = None

    text_fields: ClassVar[CSVFieldMap] = {}

    def validate(self, system: dv_file_info.DVSystem) -> str | None:
        if self.value is None:
            return "A pack value was not provided."
        if len(self.value) != 5:
            return (
                "The pack value has the wrong length: expected 5 bytes "
                f"but got {len(self.value)}."
            )
        return None

    @classmethod
    def parse_text_value(cls, text_field: str | None, text_value: str) -> NamedTuple:
        assert False

    @classmethod
    def to_text_value(cls, text_field: str | None, value_subset: NamedTuple) -> str:
        assert False

    @classmethod
    def _do_parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> Unknown | None:
        return cls(value=bytes(pack_bytes))

    @classmethod
    def parse_binary(cls, pack_bytes: bytes, system: dv_file_info.DVSystem) -> Pack | None:
        assert len(pack_bytes) == 5
        pack = cls._do_parse_binary(pack_bytes, system)
        return pack if pack is not None and pack.validate(system) is None else None

    def _do_to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        assert self.value is not None
        return self.value

    def to_binary(self, system: dv_file_info.DVSystem) -> bytes:
        validation_message = self.validate(system)
        if validation_message is not None:
            raise PackValidationError(validation_message)
        b = self._do_to_binary(system)
        assert len(b) == 5
        return b
