"""Re-applying the redaction to saved Cassettes."""

import json
from datetime import date

from evals.cassette import Cassette, CassetteEntry
from evals.redact_cassettes import main, redact_cassette


def make(tmp_path, texts):
    cassette = Cassette(date(2026, 1, 2))
    for i, text in enumerate(texts):
        body = json.dumps({"texto": text}).encode()
        key = f"GET https://x/{i}"
        cassette.entries[key] = CassetteEntry(key, 200, {"content-type": "application/json"}, body)
    path = tmp_path / "draft-a.json"
    cassette.save(path)
    return path


def test_names_left_in_a_cassette_are_numbered_across_its_entries_and_the_date_is_kept(tmp_path):
    path = make(tmp_path, ["Intimado Rui Costa", "Rui Costa e Ana Paula Ferreira"])

    changed = redact_cassette(path)

    saved = Cassette.load(path)
    assert changed
    assert saved.recorded_on == date(2026, 1, 2)
    bodies = [json.loads(e.body)["texto"] for e in saved.entries.values()]
    assert bodies == ["Intimado [PESSOA 1]", "[PESSOA 1] e [PESSOA 2]"]


def test_a_clean_cassette_is_not_rewritten(tmp_path):
    path = make(tmp_path, ["Nada a ocultar aqui"])
    before = path.read_bytes()

    assert redact_cassette(path) is False
    assert path.read_bytes() == before


def test_the_command_redacts_the_given_files_and_check_does_not_write(tmp_path):
    path = make(tmp_path, ["Autor: Rui Costa"])
    before = path.read_bytes()

    assert main(["--check", str(path)]) == 1
    assert path.read_bytes() == before
    assert main([str(path)]) == 0
    assert b"Rui Costa" not in path.read_bytes()
    assert main(["--check", str(path)]) == 0
