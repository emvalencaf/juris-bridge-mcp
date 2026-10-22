"""Resumable progress of a run: finished units of work and their stored outputs.

A run is a list of units (for example one agent run per Eval case and repetition). `Progress`
remembers each finished unit and its output in a JSON file, so a run that stopped (all keys
exhausted, request cap, Ctrl-C) can be started again and skips what it already paid for.

Typical use by a runner::

    progress = Progress(Path("evals/results/progress-tuning.json"))
    for case in cases:
        for repetition in range(3):
            output = progress.run(unit_key(case.id, repetition), lambda: run_agent(case))

A unit that raises (e.g. `AllKeysExhausted`) is not recorded; the finished ones stay on disk.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1


class ProgressError(Exception):
    """The progress file cannot be read, or an output cannot be stored."""


def unit_key(case_id: str, repetition: int) -> str:
    """Return the key of one unit of work: an Eval case id and its repetition number."""
    return f"{case_id}#{repetition}"


class Progress:
    """A JSON file of finished units and their outputs, saved after every unit.

    Outputs must be JSON-serializable. The file is written atomically (temp file, then
    rename), so a crash never leaves a half-written file. It holds outputs only, never a key.
    Keep it under `evals/results/` (git-ignored).

    Args:
        path: The JSON file; loaded if it exists, created on the first `record`.

    Raises:
        ProgressError: When an existing file is not valid progress JSON.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._units: dict[str, Any] = self._load()

    def __len__(self) -> int:
        return len(self._units)

    def is_done(self, key: str) -> bool:
        """Whether the unit finished in this or an earlier run."""
        return key in self._units

    def get(self, key: str) -> Any:
        """Return the stored output of a finished unit.

        Raises:
            KeyError: When the unit is not finished.
        """
        return self._units[key]

    def record(self, key: str, output: Any) -> None:
        """Store the output of a finished unit and save the file.

        Raises:
            ProgressError: When the output is not JSON-serializable (nothing is stored).
        """
        try:
            json.dumps(output)
        except (TypeError, ValueError) as error:
            raise ProgressError(f"output of {key!r} is not JSON-serializable") from error
        self._units[key] = output
        self._save()

    def run(self, key: str, work: Callable[[], Any]) -> Any:
        """Return the stored output if the unit is done, else call `work`, record and return it.

        Exceptions from `work` propagate and record nothing.
        """
        if key in self._units:
            return self._units[key]
        output = work()
        self.record(key, output)
        return output

    def clear(self) -> None:
        """Forget every unit and delete the file (to start a run from scratch)."""
        self._units = {}
        self._path.unlink(missing_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            units = data["units"]
            if data.get("version") != FORMAT_VERSION or not isinstance(units, dict):
                raise ValueError("unexpected format")
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ProgressError(f"cannot read progress file {self._path.name}") from error
        return units

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        payload = {"version": FORMAT_VERSION, "units": self._units}
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self._path)
