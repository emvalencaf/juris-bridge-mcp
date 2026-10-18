"""The unstable upstream payload an agent may ask for, within a size cap."""

import json
from typing import Any

MAX_RAW_BYTES = 256 * 1024


def bounded_raw(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Return the payload marked unstable, or `None` and a warning when it is too large."""
    raw = {"unstable": True, "payload": payload}
    if len(json.dumps(raw, ensure_ascii=False)) > MAX_RAW_BYTES:
        return None, f"raw payload omitted: larger than {MAX_RAW_BYTES // 1024} KiB."
    return raw, None
