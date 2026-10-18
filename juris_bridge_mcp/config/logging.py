"""Settings for the fields every wide event carries about its environment."""

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from pydantic import AliasChoices, Field
from pydantic_settings import SettingsConfigDict

from juris_bridge_mcp.config.base import EnvSettings


def _package_version() -> str:
    try:
        return version("juris-bridge-mcp")
    except PackageNotFoundError:  # pragma: no cover - running from a bare checkout
        return "unknown"


class LogSettings(EnvSettings):
    """`JURIS_BRIDGE_LOG_*`: who is logging; the region also falls back to `AWS_REGION`."""

    model_config = SettingsConfigDict(env_prefix="JURIS_BRIDGE_LOG_")

    service: str = "juris-bridge-mcp"
    version: str = Field(default_factory=_package_version)
    commit_hash: str = "unknown"
    region: str = Field(
        default="unknown",
        validation_alias=AliasChoices("JURIS_BRIDGE_LOG_REGION", "AWS_REGION"),
    )

    def environment(self) -> dict[str, Any]:
        """Return the fields stamped on every event."""
        return {
            "service": self.service,
            "version": self.version,
            "commit_hash": self.commit_hash,
            "region": self.region,
        }
