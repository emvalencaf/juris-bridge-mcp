from juris_bridge_mcp.config.datajud import DatajudSettings
from juris_bridge_mcp.config.http import HttpSettings


def test_http_defaults(monkeypatch):
    monkeypatch.delenv("JURIS_BRIDGE_HTTP_TIMEOUT_SECONDS", raising=False)

    settings = HttpSettings(_env_file=None)

    assert settings.timeout_seconds == 15
    assert settings.max_retries == 2
    assert settings.max_wait_seconds == 5


def test_datajud_defaults_to_20_second_timeout_and_120_per_minute(monkeypatch):
    monkeypatch.delenv("JURIS_BRIDGE_DATAJUD_TIMEOUT_SECONDS", raising=False)

    settings = DatajudSettings(_env_file=None)

    assert settings.timeout_seconds == 20
    assert settings.requests_per_minute == 120


def test_datajud_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv("JURIS_BRIDGE_DATAJUD_TIMEOUT_SECONDS", "30")

    assert DatajudSettings(_env_file=None).timeout_seconds == 30
