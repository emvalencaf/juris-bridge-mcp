"""The bodies of the BNP, and how their siglas map to the Court aliases of this project."""

import re

from juris_bridge_mcp.domain.courts import DATAJUD_COURTS
from juris_bridge_mcp.domain.errors import invalid_argument

# STF is a Court of this project only for Precedents: DataJud does not publish its Cases.
PRECEDENT_COURTS = ("stf", *DATAJUD_COURTS)

# BNP bodies with no Court alias here; they are kept under their sigla with no `court`.
BODIES_WITHOUT_ALIAS = ("TNU",)

_NUMBERED = re.compile(r"^(trf|trt)(\d+)$")
_ELECTORAL = "tre-"


def body_for_court(alias: str) -> str:
    """Return the BNP sigla of a Court alias, such as `trf1` -> `TRF01` or `tjdft` -> `TJDF`."""
    if alias == "tjdft":
        return "TJDF"
    if alias.startswith(_ELECTORAL):
        return "TRE_" + alias.removeprefix(_ELECTORAL).upper()
    numbered = _NUMBERED.match(alias)
    if numbered:
        return f"{numbered[1].upper()}{int(numbered[2]):02d}"
    return alias.upper()


_COURT_BY_BODY = {body_for_court(alias): alias for alias in PRECEDENT_COURTS}


def court_for_body(sigla: str) -> str | None:
    """Return the Court alias of a BNP sigla, or `None` when the body has no alias here."""
    return _COURT_BY_BODY.get(sigla.strip().upper())


def resolve_precedent_court(alias: str) -> str:
    """Return the canonical alias for `alias`, or raise `invalid_argument`."""
    key = alias.strip().lower()
    if key not in PRECEDENT_COURTS:
        raise invalid_argument(
            f"Unknown court alias: {alias!r}",
            hint="Valid aliases: " + ", ".join(PRECEDENT_COURTS),
        )
    return key
