import pytest
from pydantic import ValidationError

from juris_bridge_mcp.config.server import ServerSettings


def test_refuses_to_load_without_api_key(monkeypatch):
    monkeypatch.delenv("JURIS_BRIDGE_SERVER_API_KEYS", raising=False)

    with pytest.raises(ValidationError):
        ServerSettings(_env_file=None)


def test_refuses_blank_api_keys(monkeypatch):
    monkeypatch.setenv("JURIS_BRIDGE_SERVER_API_KEYS", " , ")

    with pytest.raises(ValidationError):
        ServerSettings(_env_file=None)


def test_splits_comma_separated_keys(monkeypatch):
    monkeypatch.setenv("JURIS_BRIDGE_SERVER_API_KEYS", "alpha, beta ,gamma")

    assert ServerSettings(_env_file=None).keys() == ("alpha", "beta", "gamma")


def test_reads_host_and_port_from_prefixed_env(monkeypatch):
    monkeypatch.setenv("JURIS_BRIDGE_SERVER_API_KEYS", "k")
    monkeypatch.setenv("JURIS_BRIDGE_SERVER_PORT", "9001")

    assert ServerSettings(_env_file=None).port == 9001
