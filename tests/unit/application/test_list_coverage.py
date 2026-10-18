from juris_bridge_mcp.adapters.static_coverage_catalog import (
    StaticCoverageCatalog,
)
from juris_bridge_mcp.application.use_cases.list_coverage import list_coverage


def _coverage():
    return list_coverage(StaticCoverageCatalog())


def test_states_each_source_with_its_supported_operations():
    coverage = {s["source"]: s for s in _coverage()["sources"]}

    assert set(coverage) == {"datajud", "senado"}
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
    assert {"tre-sp", "tre-dft", "tjmmg", "tjmrs", "tjmsp"} <= aliases
    assert len(aliases) == 91
