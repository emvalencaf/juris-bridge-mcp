"""Key selection, the seam where key rotation (#96) plugs in. Only one key for now."""

from dataclasses import dataclass, field
from typing import Protocol

from pydantic import SecretStr


@dataclass(frozen=True)
class ApiKey:
    """An API key and the alias that stands for it in logs and reports.

    Attributes:
        alias: Safe name of the key (e.g. `key-1`).
        secret: The key; hidden from `repr` and `str`.
    """

    alias: str
    secret: SecretStr = field(repr=False)


class KeySource(Protocol):
    """Chooses the key that serves the next request."""

    def current(self) -> ApiKey:
        """Return the key to use now."""
        ...

    def mark_exhausted(self, key: ApiKey) -> None:
        """Tell the source the key has no quota left (rotation reacts; a single key does not)."""
        ...


class SingleKeySource:
    """The only implementation for now: always the same key."""

    def __init__(self, secret: SecretStr, alias: str = "key-1") -> None:
        self._key = ApiKey(alias=alias, secret=secret)

    def current(self) -> ApiKey:
        """Return the one key."""
        return self._key

    def mark_exhausted(self, key: ApiKey) -> None:
        """Do nothing: there is no other key to move to."""
