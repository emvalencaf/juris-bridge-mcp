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
    # Seconds a parsed norm text is kept in memory, so paging a long norm fetches it once.
    cache_ttl_seconds: float = 3600
    # Pages weigh megabytes once parsed, so keep few of them.
    cache_max_entries: int = 16
