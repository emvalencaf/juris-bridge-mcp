"""Settings for the BNP provider."""

from pydantic_settings import SettingsConfigDict

from juris_bridge_mcp.config.base import EnvSettings


class BnpSettings(EnvSettings):
    """`JURIS_BRIDGE_BNP_*`: the keyless read backend of the Banco Nacional de Precedentes."""

    model_config = SettingsConfigDict(env_prefix="JURIS_BRIDGE_BNP_")

    base_url: str = "https://pangeabnp.pdpj.jus.br/api/v1"
    timeout_seconds: float = 30
    # The BNP documents no limit; a few requests per second at most keeps the load light.
    requests_per_minute: int = 60
    # The BNP is updated twice a month, so a lookup can be kept for hours.
    cache_ttl_seconds: float = 3600
    cache_max_entries: int = 256
