"""Settings for the Câmara Legin provider."""

from pydantic_settings import SettingsConfigDict

from juris_bridge_mcp.config.base import EnvSettings


class LeginSettings(EnvSettings):
    """`JURIS_BRIDGE_LEGIN_*`: the LexML URN page and the Câmara Legin pages, which need no key."""

    model_config = SettingsConfigDict(env_prefix="JURIS_BRIDGE_LEGIN_")

    # The page that resolves a URN Lex to the Legin sheet; its `/urn` path is allowed by robots.txt.
    lexml_base_url: str = "https://www.lexml.gov.br"
    timeout_seconds: float = 30
    # LexML asks for a crawl delay of 5 s; a norm costs three requests (URN page, sheet, text).
    requests_per_minute: int = 12
