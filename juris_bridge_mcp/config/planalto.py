"""Settings for the Planalto provider."""

from pydantic_settings import SettingsConfigDict

from juris_bridge_mcp.config.base import EnvSettings


class PlanaltoSettings(EnvSettings):
    """`JURIS_BRIDGE_PLANALTO_*`: the static norm pages, which need no key."""

    model_config = SettingsConfigDict(env_prefix="JURIS_BRIDGE_PLANALTO_")

    base_url: str = "https://www.planalto.gov.br/ccivil_03"
    timeout_seconds: float = 30
    # No rate limit is published; stay polite with a page that can weigh megabytes.
    requests_per_minute: int = 60
