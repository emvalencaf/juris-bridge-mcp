"""Re-apply the redaction to Cassettes already saved, offline.

    uv run --group evals python -m evals.redact_cassettes [--check] [file ...]

With no file it takes `evals/cassettes/draft-*.json`. Each Cassette gets a fresh `Redactor`, so
the people left in it are numbered `[PESSOA N]` across all its entries; the `recorded_on` date
and the keys are kept, and a Cassette that would not change is not rewritten. `--check` writes
nothing and exits 1 if any Cassette would change.

A placeholder from the earlier heuristic redaction (`[NOME]`) is kept as it is: the name it
replaced is gone, so it cannot be numbered or restored. Re-record the Cassette to get that.
"""

import argparse
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from evals.cassette import CASSETTES_DIR, Cassette
from evals.record import redact_body
from evals.redaction import Redactor


def redact_cassette(path: Path, *, write: bool = True) -> bool:
    """Redact every entry of the Cassette at `path`; return whether anything changed."""
    cassette = Cassette.load(path)
    redactor = Redactor()
    changed = False
    for key, entry in cassette.entries.items():
        body = redact_body(redactor, entry.body, entry.headers.get("content-type", ""))
        if body != entry.body:
            changed = True
            cassette.entries[key] = replace(entry, body=body)
    if changed and write:
        cassette.save(path)
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; return the exit code."""
    parser = argparse.ArgumentParser(prog="python -m evals.redact_cassettes", description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 on a change")
    args = parser.parse_args(argv)
    files = args.files or sorted(CASSETTES_DIR.glob("draft-*.json"))
    changed = [path for path in files if redact_cassette(path, write=not args.check)]
    verb = "would change" if args.check else "redacted"
    for path in changed:
        print(f"{verb}: {path}")
    print(f"{len(changed)} of {len(files)} Cassettes {verb if changed else 'unchanged'}")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
