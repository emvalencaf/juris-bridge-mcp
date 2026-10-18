"""Settings for outbound HTTP calls shared by all providers."""

from pydantic_settings import SettingsConfigDict

from juris_bridge_mcp.config.base import EnvSettings


class HttpSettings(EnvSettings):
    """`JURIS_BRIDGE_HTTP_*`: transport behaviour for upstream calls."""

    model_config = SettingsConfigDict(env_prefix="JURIS_BRIDGE_HTTP_")

    timeout_seconds: float = 15
