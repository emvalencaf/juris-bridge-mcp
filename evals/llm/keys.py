"""Key selection: one key as-is, or opt-in rotation across several keys."""

from dataclasses import dataclass, field
from typing import Protocol

from pydantic import SecretStr

from evals.llm.errors import AllKeysExhausted
from evals.llm.settings import EvalLLMSettings


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
        """Return the key to use now.

        Raises:
            AllKeysExhausted: When rotation has no key left.
        """
        ...

    def mark_exhausted(self, key: ApiKey) -> None:
        """Tell the source the key has no quota left (rotation reacts; a single key does not)."""
        ...


class SingleKeySource:
    """Always the same key; running out of quota is handled by retrying, as before."""

    def __init__(self, secret: SecretStr, alias: str = "key-1") -> None:
        self._key = ApiKey(alias=alias, secret=secret)

    def current(self) -> ApiKey:
        """Return the one key."""
        return self._key

    def mark_exhausted(self, key: ApiKey) -> None:
        """Do nothing: there is no other key to move to."""


class RotatingKeySource:
    """Uses the keys in order and moves to the next when one is marked exhausted.

    Keys are aliased `key-1`, `key-2`, ... by position. A key stays skipped for the life of
    the source (the daily quota resets only at midnight Pacific time). Quotas are per project:
    rotating helps only when the keys belong to different projects.

    Args:
        secrets: The keys, in the order to use them.
    """

    def __init__(self, secrets: list[SecretStr]) -> None:
        self._keys = [ApiKey(alias=f"key-{i}", secret=s) for i, s in enumerate(secrets, start=1)]
        self._exhausted: set[str] = set()

    def current(self) -> ApiKey:
        """Return the first key not yet exhausted.

        Raises:
            AllKeysExhausted: When every key is exhausted.
        """
        for key in self._keys:
            if key.alias not in self._exhausted:
                return key
        raise AllKeysExhausted(f"all {len(self._keys)} API keys are out of daily quota")

    def mark_exhausted(self, key: ApiKey) -> None:
        """Skip the key from now on."""
        self._exhausted.add(key.alias)


def key_source_from(settings: EvalLLMSettings) -> KeySource:
    """Build the key source the settings ask for.

    Rotation is off unless `EVALS_ROTATE_KEYS` is true and more than one key is given; with
    rotation off only the first key is used.

    Raises:
        ValueError: When no key is configured.
    """
    secrets = settings.api_keys()
    if not secrets:
        raise ValueError("no API key: set GEMINI_API_KEY (or GEMINI_API_KEYS)")
    if settings.rotate_keys and len(secrets) > 1:
        return RotatingKeySource(secrets)
    return SingleKeySource(secrets[0])
