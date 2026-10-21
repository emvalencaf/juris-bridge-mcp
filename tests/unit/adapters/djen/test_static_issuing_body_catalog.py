import json
from importlib import resources

from juris_bridge_mcp.adapters.djen.static_issuing_body_catalog import (
    CATALOG_FILE,
    StaticIssuingBodyCatalog,
)
from juris_bridge_mcp.domain.publication_courts import DJEN_COURTS


def test_reads_the_ids_of_a_court_and_the_version_of_the_document():
    catalog = StaticIssuingBodyCatalog(
        {"version": "2026-10-21.1", "courts": {"tjsp": [{"id": 7, "name": "A"}, {"id": 9}]}}
    )

    assert catalog.version == "2026-10-21.1"
    assert catalog.body_ids("tjsp") == (7, 9)


def test_a_court_without_an_entry_has_no_bodies():
    assert StaticIssuingBodyCatalog({"version": "0", "courts": {}}).body_ids("tjsp") == ()


def test_the_shipped_file_loads():
    assert StaticIssuingBodyCatalog().version


def test_the_shipped_catalog_lists_only_djen_courts_with_distinct_positive_ids():
    document = json.loads(
        resources.files("juris_bridge_mcp.adapters.djen").joinpath(CATALOG_FILE).read_text("utf-8")
    )
    catalog = StaticIssuingBodyCatalog(document)

    assert set(document["courts"]) <= set(DJEN_COURTS)
    for court in document["courts"]:
        ids = catalog.body_ids(court)
        assert ids and len(set(ids)) == len(ids) and all(i > 0 for i in ids)
