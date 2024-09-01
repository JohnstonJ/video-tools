from typing import Any, ClassVar, Protocol


# see https://stackoverflow.com/a/55240861
class DataclassInstance(Protocol):
    """Type annotation that indicates something must be a dataclass."""

    __dataclass_fields__: ClassVar[dict[str, Any]]
