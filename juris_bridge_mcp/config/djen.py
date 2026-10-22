"""Settings for the DJEN provider."""

from pydantic_settings import SettingsConfigDict

from juris_bridge_mcp.config.base import EnvSettings


class DjenSettings(EnvSettings):
    """`JURIS_BRIDGE_DJEN_*`: the keyless public read API of the DJEN."""

    model_config = SettingsConfigDict(env_prefix="JURIS_BRIDGE_DJEN_")

    base_url: str = "https://comunicaapi.pje.jus.br"
    timeout_seconds: float = 20
    # The DJEN allows about 20 requests per IP in a window it does not document, blocks
    # abuse and answers 429 above it; stay under it.
    requests_per_minute: int = 15
