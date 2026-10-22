from juris_bridge_mcp.config.logging import LogSettings


def test_region_falls_back_to_aws_region(monkeypatch):
    monkeypatch.delenv("JURIS_BRIDGE_LOG_REGION", raising=False)
    monkeypatch.setenv("AWS_REGION", "sa-east-1")

    assert LogSettings(_env_file=None).environment()["region"] == "sa-east-1"


def test_log_prefixed_values_win(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "sa-east-1")
    monkeypatch.setenv("JURIS_BRIDGE_LOG_REGION", "us-east-1")
    monkeypatch.setenv("JURIS_BRIDGE_LOG_COMMIT_HASH", "deadbee")

    env = LogSettings(_env_file=None).environment()

    assert (env["region"], env["commit_hash"], env["service"]) == (
        "us-east-1",
        "deadbee",
        "juris-bridge-mcp",
    )
