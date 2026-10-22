"""Settings for the HTTP server and its Bearer authentication."""

from pydantic import SecretStr, field_validator
from pydantic_settings import SettingsConfigDict

from juris_bridge_mcp.config.base import EnvSettings


class ServerSettings(EnvSettings):
    """`JURIS_BRIDGE_SERVER_*`: bind address and the accepted API keys."""

    model_config = SettingsConfigDict(env_prefix="JURIS_BRIDGE_SERVER_")

    host: str = "0.0.0.0"  # noqa: S104 - container-first: bind all interfaces
    port: int = 8000
    api_keys: SecretStr

    @field_validator("api_keys")
    @classmethod
    def _require_a_key(cls, value: SecretStr) -> SecretStr:
        if not _split(value.get_secret_value()):
            raise ValueError("at least one API key is required")
        return value

    def keys(self) -> tuple[str, ...]:
        """Return the configured API keys, trimmed and without blanks."""
        return _split(self.api_keys.get_secret_value())


def _split(raw: str) -> tuple[str, ...]:
    return tuple(key for key in (part.strip() for part in raw.split(",")) if key)
