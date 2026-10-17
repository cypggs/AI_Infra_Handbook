"""Entity (primary key) model for feature tables.

An entity is the join key that links raw events, offline feature rows
and online feature values together, e.g. ``user_id`` or ``item_id``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Entity:
    """Logical entity a feature table describes.

    Attributes:
        name: Human readable name, e.g. ``"user"``.
        join_key: Column name used as the primary key, e.g. ``"user_id"``.
        description: Optional documentation string.
    """

    name: str
    join_key: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("entity name must not be empty")
        if not self.join_key:
            raise ValueError("entity join_key must not be empty")

    def key_of(self, row: dict) -> str:
        """Extract the entity key from a raw record."""
        if self.join_key not in row:
            raise KeyError(f"record missing join key {self.join_key!r}")
        return str(row[self.join_key])
