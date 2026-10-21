from juris_bridge_mcp.adapters.djen.static_issuing_body_catalog import StaticIssuingBodyCatalog


def test_reads_the_ids_of_a_court_and_the_version_of_the_document():
    catalog = StaticIssuingBodyCatalog(
        {"version": "2026-10-21.1", "courts": {"tjsp": [{"id": 7, "name": "A"}, {"id": 9}]}}
    )

    assert catalog.version == "2026-10-21.1"
    assert catalog.organ_ids("tjsp") == (7, 9)


def test_a_court_without_an_entry_has_no_bodies():
    assert StaticIssuingBodyCatalog({"version": "0", "courts": {}}).organ_ids("tjsp") == ()


def test_the_shipped_file_loads():
    assert StaticIssuingBodyCatalog().version
