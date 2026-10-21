"""The Issuing bodies of the DJEN Courts, read from the catalog file shipped with the server."""

import json
from importlib import resources
from typing import Any

CATALOG_FILE = "issuing_bodies.json"


class StaticIssuingBodyCatalog:
    """Reads `issuing_bodies.json`: a `version`, its `generated_on` date and `courts`.

    Each Court maps to a list of `{"id": <orgaoId>, "name": <nomeOrgao>}`. The file is built by
    `scripts/build_issuing_body_catalog.py` and holds no publication text and no party names.
    """

    def __init__(self, document: dict[str, Any] | None = None) -> None:
        if document is None:
            document = json.loads(
                resources.files(__package__).joinpath(CATALOG_FILE).read_text("utf-8")
            )
        self._version = str(document["version"])
        self._courts = {
            court: tuple(int(body["id"]) for body in bodies)
            for court, bodies in document["courts"].items()
        }

    @property
    def version(self) -> str:
        """Return the catalog version, which changes with its content."""
        return self._version

    def organ_ids(self, court: str) -> tuple[int, ...]:
        """Return the Court's known `orgaoId`, or an empty tuple when it has no entry."""
        return self._courts.get(court, ())
