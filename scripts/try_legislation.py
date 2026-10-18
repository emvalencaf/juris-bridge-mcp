#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["fastmcp>=4.1.0", "httpx>=0.28.1", "pydantic-settings>=2.16.0"]
# ///
"""Try `get_legislation` against the live Senado and Planalto, with no server to start.

Builds the real server in-process and calls the tool through an MCP client, so what you
see is what an agent receives. Run it with no arguments for a guided session, or pass flags:

    scripts/try_legislation.py                                  # guided
    scripts/try_legislation.py URN                              # metadata only
    scripts/try_legislation.py URN --text [--max-chars N]       # norm text, first slice
    scripts/try_legislation.py URN --article "Art. 5º"          # one article
    scripts/try_legislation.py URN --text --all                 # follow the cursor to the end

Exit code is 1 when the tool returns an error. No DataJud key is needed.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import Client

from juris_bridge_mcp.config.datajud import DatajudSettings
from juris_bridge_mcp.config.http import HttpSettings
from juris_bridge_mcp.config.legin import LeginSettings
from juris_bridge_mcp.config.planalto import PlanaltoSettings
from juris_bridge_mcp.config.senado import SenadoSettings
from juris_bridge_mcp.infrastructure.bootstrap import build_server

EXAMPLE_URN = "urn:lex:br:federal:lei:2021-04-01;14133"
PREVIEW_CHARS = 600


async def call(client: Client, arguments: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Call the tool; return `(ok, payload)` where payload is the result or the error body."""
    result = await client.call_tool("get_legislation", arguments, raise_on_error=False)
    if result.is_error:
        return False, json.loads(result.content[0].text)
    return True, result.data


def show(ok: bool, payload: dict[str, Any], *, full: bool) -> None:
    """Print a result: the fields that matter, then the text (cut unless `full`)."""
    if not ok:
        print(
            f"\nERROR  {payload['code']}  "
            f"(source: {payload['source']}, retryable: {payload['retryable']})"
        )
        print(f"  {payload['message']}")
        if payload.get("hint"):
            print(f"  hint: {payload['hint']}")
        return
    print(f"\n{payload['name']}  [{payload['content_kind']}]")
    print(f"  citation : {payload['citation']['text']} <{payload['citation']['url']}>")
    print(f"  relations: {len(payload['relations'])} of {payload['relations_total']}")
    for warning in payload["warnings"]:
        print(f"  WARNING  : {warning}")
    if "text" not in payload:
        return
    text = payload["text"]
    if "article" in payload:
        print(f"  article  : {payload['article']['label']}  flags={payload['article']['flags']}")
    print(
        f"  text     : {len(text)} chars  truncated={payload['truncated']}  "
        f"from {payload['text_url']}"
    )
    shown = text if full or len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS] + " [...]"
    print("  " + "-" * 60)
    print("  " + shown.replace("\n", "\n  "))
    print("  " + "-" * 60)


async def run(arguments: dict[str, Any], *, follow: bool, full: bool) -> bool:
    """Run one call (and, with `follow`, every slice after it); return whether all succeeded."""
    settings = {
        "datajud": DatajudSettings(api_key="unused"),
        "http": HttpSettings(),
        "senado": SenadoSettings(),
        "planalto": PlanaltoSettings(),
        "legin": LeginSettings(),
    }
    async with Client(build_server(**settings)) as client:
        while True:
            ok, payload = await call(client, arguments)
            show(ok, payload, full=full)
            cursor = payload.get("next_text_cursor") if ok else None
            if not ok or not cursor:
                return ok
            if not follow and not _ask_yes("\nRead the next slice?", default=False):
                print(f"  next_text_cursor: {cursor}")
                return ok
            arguments = {**arguments, "text_cursor": cursor}


def _ask(question: str, default: str) -> str:
    answer = input(f"{question} [{default}]: ").strip()
    return answer or default


def _ask_yes(question: str, *, default: bool) -> bool:
    answer = input(f"{question} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not answer else answer.startswith("y")


def guided() -> tuple[dict[str, Any], bool, bool]:
    """Ask what to fetch; return the tool arguments and the `follow` and `full` switches."""
    print("get_legislation, live. Press Enter to accept a default.\n")
    urn = _ask("URN Lex", EXAMPLE_URN)
    print("  1) metadata only   2) norm text   3) one article")
    mode = _ask("What do you want", "3")
    arguments: dict[str, Any] = {"urn": urn}
    if mode == "2":
        arguments.update(include_text=True, max_chars=int(_ask("Characters per slice", "2000")))
    elif mode == "3":
        arguments["article"] = _ask("Article", "Art. 5º")
    return arguments, False, mode == "3"


def parse_args(argv: list[str]) -> tuple[dict[str, Any], bool, bool]:
    """Read the flags; return the tool arguments and the `follow` and `full` switches."""
    parser = argparse.ArgumentParser(description="Try get_legislation against the live Sources.")
    parser.add_argument("urn")
    parser.add_argument("--text", action="store_true", help="include the norm text")
    parser.add_argument("--article", help="return one article, e.g. 'Art. 5º'")
    parser.add_argument("--max-chars", type=int, help="slice size (default: the tool's)")
    parser.add_argument("--cursor", help="continue from a next_text_cursor")
    parser.add_argument("--all", action="store_true", help="follow the cursor to the end")
    parser.add_argument("--full", action="store_true", help="print the whole text, not a preview")
    parser.add_argument("--raw", action="store_true", help="attach the upstream Senado payload")
    args = parser.parse_args(argv)
    arguments: dict[str, Any] = {"urn": args.urn, "include_text": args.text}
    if args.article:
        arguments["article"] = args.article
    if args.max_chars:
        arguments["max_chars"] = args.max_chars
    if args.cursor:
        arguments["text_cursor"] = args.cursor
    if args.raw:
        arguments["include_raw"] = True
    return arguments, args.all, args.full or bool(args.article)


def main() -> int:
    """Entry point: guided without arguments, flags otherwise."""
    arguments, follow, full = guided() if len(sys.argv) == 1 else parse_args(sys.argv[1:])
    return 0 if asyncio.run(run(arguments, follow=follow, full=full)) else 1


if __name__ == "__main__":
    sys.exit(main())
