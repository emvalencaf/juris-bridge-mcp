"""Settings for the Senado provider."""

from pydantic_settings import SettingsConfigDict

from juris_bridge_mcp.config.base import EnvSettings


class SenadoSettings(EnvSettings):
    """`JURIS_BRIDGE_SENADO_*`: the open-data endpoint, which needs no key."""

    model_config = SettingsConfigDict(env_prefix="JURIS_BRIDGE_SENADO_")

    base_url: str = "https://legis.senado.leg.br/dadosabertos"
    timeout_seconds: float = 20
    # The Senado answers 429 above 10 requests per second; stay well under it.
    requests_per_minute: int = 300
    # Seconds a search is kept in memory so its pages cost one request, and how many at most.
    cache_ttl_seconds: float = 300
    cache_max_entries: int = 64
