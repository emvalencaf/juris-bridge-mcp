#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["fastmcp>=4.1.0", "httpx>=0.28.1"]
# ///
"""Build the catalog of Issuing bodies (`orgaoId`) of the DJEN Courts (ADR 0007).

The DJEN has no endpoint listing them, so this reads `idOrgao` and `nomeOrgao` from the first
page of recent days of each Court and merges them into `issuing_bodies.json`. A page shows
only 100 items, so a day with more is also probed with common words, each surfacing other
bodies. The file is saved after each Court, so an interrupted run keeps what it read.
Only ids and body names are kept: no publication text, no party names.

Run it by hand, paced to the DJEN limit of about 20 requests per window:

    scripts/build_issuing_body_catalog.py                       # every Court, last 5 days
    scripts/build_issuing_body_catalog.py --courts tjsp trf1 --days 10
    scripts/build_issuing_body_catalog.py --dry-run             # print, write nothing

The merge is additive: bodies already in the file are kept. When the file changes its
`version` becomes the generation date plus a counter, which invalidates older Cursors.
Exit code is 1 on an HTTP failure; Courts already read stay saved.
"""

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from juris_bridge_mcp.domain.publication_courts import DJEN_COURTS

CATALOG = (
    Path(__file__).resolve().parent.parent / "juris_bridge_mcp/adapters/djen/issuing_bodies.json"
)
BASE_URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
# 15 requests a minute, under the DJEN's undocumented window of about 20.
PACE_SECONDS = 4.0
# Words common in decisions; each narrows a capped day to other items.
# Checked live: on a TJSP day the first page showed 44 bodies and these five found 61 more.
PROBES = (
    "recurso",
    "sentença",
    "acórdão",
    "decisão",
    "processo",
    "execução",
    "agravo",
    "embargos",
)
PAGE_SIZE = 100


def _fetch(client: httpx.Client, params: dict[str, str | int]) -> dict:
    time.sleep(PACE_SECONDS)
    response = client.get(BASE_URL, params=params)
    if response.status_code == 429:
        print("429: waiting 60 s", file=sys.stderr)
        time.sleep(60)
        response = client.get(BASE_URL, params=params)
    response.raise_for_status()
    return response.json()


def _bodies(body: dict) -> dict[int, str]:
    found: dict[int, str] = {}
    for item in body.get("items", []):
        organ = item.get("idOrgao")
        if isinstance(organ, int) and not isinstance(organ, bool):
            found[organ] = str(item.get("nomeOrgao") or "")
    return found


def _collect(client: httpx.Client, court: str, days: int) -> dict[int, str]:
    found: dict[int, str] = {}
    for offset in range(1, days + 1):
        day = (date.today() - timedelta(days=offset)).isoformat()
        params: dict[str, str | int] = {
            "siglaTribunal": court.upper(),
            "dataDisponibilizacaoInicio": day,
            "dataDisponibilizacaoFim": day,
            "itensPorPagina": PAGE_SIZE,
            "pagina": 1,
        }
        body = _fetch(client, params)
        found |= _bodies(body)
        # A full first page hides the bodies of the items past it, not only on capped days.
        if body.get("count", 0) >= PAGE_SIZE:
            for word in PROBES:
                found |= _bodies(_fetch(client, {**params, "texto": word}))
        print(f"{court} {day}: {len(found)} bodies so far", file=sys.stderr)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--courts", nargs="+", default=list(DJEN_COURTS), metavar="ALIAS")
    parser.add_argument("--days", type=int, default=5, help="recent days to read per Court")
    parser.add_argument("--dry-run", action="store_true", help="print the catalog, write nothing")
    args = parser.parse_args()

    catalog = json.loads(CATALOG.read_text("utf-8"))
    courts: dict[str, dict[int, str]] = {
        court: {body["id"]: body["name"] for body in bodies}
        for court, bodies in catalog["courts"].items()
    }
    before = json.dumps(catalog["courts"], sort_keys=True)

    def save() -> None:
        merged = {
            court: [{"id": organ, "name": name} for organ, name in sorted(bodies.items())]
            for court, bodies in sorted(courts.items())
            if bodies
        }
        if json.dumps(merged, sort_keys=True) == before or catalog["courts"] == merged:
            return
        if catalog["version"].split(".")[0] != date.today().isoformat():
            number = int(catalog["version"].rpartition(".")[2] or 0)
            catalog["version"] = f"{date.today().isoformat()}.{number + 1}"
        catalog["generated_on"] = date.today().isoformat()
        catalog["courts"] = merged
        if not args.dry_run:
            CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", "utf-8")

    try:
        with httpx.Client(timeout=30) as client:
            for court in args.courts:
                courts.setdefault(court, {}).update(_collect(client, court, args.days))
                save()
    except httpx.HTTPError as failure:
        print(f"DJEN request failed: {failure}", file=sys.stderr)
        return 1
    if args.dry_run:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
    else:
        print(f"{CATALOG}: version {catalog['version']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
