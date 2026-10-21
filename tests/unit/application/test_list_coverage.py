from datetime import date, timedelta

import pytest

from juris_bridge_mcp.adapters.static_coverage_catalog import (
    StaticCoverageCatalog,
)
from juris_bridge_mcp.application.use_cases.list_coverage import list_coverage
from juris_bridge_mcp.domain.errors import ToolFailure
from juris_bridge_mcp.domain.publication_courts import resolve_djen_court


def _coverage():
    return list_coverage(StaticCoverageCatalog())


def test_states_each_source_with_its_supported_operations():
    coverage = {s["source"]: s for s in _coverage()["sources"]}

    assert set(coverage) == {"datajud", "djen", "senado"}
    assert coverage["datajud"]["kind"] == "cases"
    assert coverage["senado"]["kind"] == "legislation"


def test_every_court_has_citation_url_false():
    courts = [c for s in _coverage()["sources"] for c in s["courts"]]

    assert courts
    assert all(c["citation_url"] is False for c in courts)


def test_stf_is_listed_as_not_supported():
    datajud = next(s for s in _coverage()["sources"] if s["source"] == "datajud")
    stf = next(c for c in datajud["courts"] if c["alias"] == "stf")

    assert stf["supported"] is False


def test_covers_the_documented_datajud_aliases():
    datajud = next(s for s in _coverage()["sources"] if s["source"] == "datajud")
    aliases = {c["alias"] for c in datajud["courts"] if c["supported"]}

    assert {"tst", "tse", "stj", "stm", "trf1", "trf6", "tjsp", "tjdft", "trt24"} <= aliases
    assert {"tre-sp", "tre-df", "tjmmg", "tjmrs", "tjmsp"} <= aliases
    assert len(aliases) == 91


def _djen(alias):
    djen = next(s for s in _coverage()["sources"] if s["source"] == "djen")
    return next(c for c in djen["courts"] if c["alias"] == alias)


def test_a_covered_djen_court_states_its_known_start():
    assert _djen("tjsp") == {
        "alias": "tjsp",
        "supported": True,
        "citation_url": False,
        "available_from": "2025-03-01",
    }


def test_a_djen_court_without_a_known_start_omits_the_date():
    court = _djen("tjba")

    assert court["supported"] is True and "available_from" not in court


def test_stf_and_the_tres_are_not_covered_by_the_djen_each_with_its_reason():
    stf, tre = _djen("stf"), _djen("tre-sp")

    assert stf["supported"] is tre["supported"] is False
    assert stf["reason"] and tre["reason"] and stf["reason"] != tre["reason"]


def test_a_source_that_has_no_dates_or_reasons_does_not_emit_them():
    tjsp = next(
        c
        for s in _coverage()["sources"]
        if s["source"] == "datajud"
        for c in s["courts"]
        if c["alias"] == "tjsp"
    )

    assert tjsp == {"alias": "tjsp", "supported": True, "citation_url": False}


def test_the_catalog_and_the_resolver_agree_on_who_is_covered():
    djen = next(s for s in _coverage()["sources"] if s["source"] == "djen")
    for court in djen["courts"]:
        if court["supported"]:
            assert resolve_djen_court(court["alias"], date(2030, 1, 1)) == court["alias"]
        else:
            with pytest.raises(ToolFailure):
                resolve_djen_court(court["alias"], date(2030, 1, 1))


def test_a_date_before_the_start_the_catalog_states_is_not_covered():
    start = date.fromisoformat(_djen("tjsp")["available_from"])

    with pytest.raises(ToolFailure):
        resolve_djen_court("tjsp", start - timedelta(days=1))
    assert resolve_djen_court("tjsp", start) == "tjsp"
