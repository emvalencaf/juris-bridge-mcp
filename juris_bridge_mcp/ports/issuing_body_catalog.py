"""Port: where the Issuing bodies of a Court come from."""

from typing import Protocol


class IssuingBodyCatalog(Protocol):
    """Provides the known `orgaoId` of each Court; never touches the network.

    The DJEN exposes no endpoint listing them, so the catalog is built offline and shipped
    with the server (ADR 0007). `version` changes whenever its content does.
    """

    @property
    def version(self) -> str:
        """Return the catalog version, which changes with its content."""
        ...

    def body_ids(self, court: str) -> tuple[int, ...]:
        """Return the Court's known `orgaoId`, or an empty tuple when it has no entry."""
        ...
