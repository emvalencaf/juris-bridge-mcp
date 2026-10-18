"""Settings for the DataJud provider."""

from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from juris_bridge_mcp.config.base import EnvSettings


class DatajudSettings(EnvSettings):
    """`JURIS_BRIDGE_DATAJUD_*`: endpoint and the user's own DataJud key."""

    model_config = SettingsConfigDict(env_prefix="JURIS_BRIDGE_DATAJUD_")

    base_url: str = "https://api-publica.datajud.cnj.jus.br"
    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = 20
    requests_per_minute: int = 120
