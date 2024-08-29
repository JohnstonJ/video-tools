from typing import TypeVar, cast

T = TypeVar("T")


def hex_int(int_value: int, digits: int, skip_prefix: bool = False) -> str:
    return f"0x{int_value:0{digits}X}" if not skip_prefix else f"{int_value:0{digits}X}"


def hex_bytes(bytes_value: bytes | list[int | None], allow_optional: bool = False) -> str:
    return "0x" + "".join(
        [
            (
                hex_int(cast(int, b), 2, skip_prefix=True)
                if not allow_optional or b is not None
                else "__"
            )
            for b in bytes_value
        ]
    )


def parse_bool(text_value: str) -> bool:
    if text_value.upper() == "TRUE":
        return True
    elif text_value.upper() == "FALSE":
        return False
    raise ValueError("Invalid boolean format.")


# Add/remove field prefixes from simple field name strings


def field_has_prefix(prefix: str, prefixed_field: str, excluded_prefixes: list[str] = []) -> bool:
    if any(
        [
            prefixed_field.startswith(f"{exclusion}") or prefixed_field == exclusion
            for exclusion in excluded_prefixes
        ]
    ):
        return False
    return prefix == prefixed_field or prefixed_field.startswith(f"{prefix}_")


def remove_field_prefix(prefix: str, prefixed_field: str) -> str | None:
    return None if prefix == prefixed_field else prefixed_field.removeprefix(f"{prefix}_")


# Add/remove field prefixes from dictionary keys


def add_field_prefix(prefix: str, unprefixed_fields: dict[str | None, T]) -> dict[str, T]:
    return {
        f"{prefix}_field_name" if field_name is not None else prefix: value
        for field_name, value in unprefixed_fields.items()
    }


def select_field_prefix(
    prefix: str, prefixed_fields: dict[str, T], excluded_prefixes: list[str] = []
) -> dict[str | None, T]:
    """Choose only dictionary items with the given prefix, and then remove the prefix.

    A set of excluded prefixes can be provided.  Typically these excluded prefixes are longer and
    will be prefixed with the requested prefix.
    """
    excluded = {
        field_name: value
        for field_name, value in prefixed_fields.items()
        if not any(
            [
                field_name.startswith(f"{exclusion}") or field_name == exclusion
                for exclusion in excluded_prefixes
            ]
        )
    }
    return {
        None if field_name == prefix else field_name.removeprefix(f"{prefix}_"): value
        for field_name, value in excluded.items()
        if (field_name.startswith(f"{prefix}_") or field_name == prefix)
    }
