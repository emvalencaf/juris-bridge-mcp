"""Entry point: reads settings, prints the notice and starts the server."""

import sys

import uvicorn
from pydantic import ValidationError

from juris_bridge_mcp.adapters.wide_event import configure_logger
from juris_bridge_mcp.config.datajud import DatajudSettings
from juris_bridge_mcp.config.http import HttpSettings
from juris_bridge_mcp.config.legin import LeginSettings
from juris_bridge_mcp.config.logging import LogSettings
from juris_bridge_mcp.config.planalto import PlanaltoSettings
from juris_bridge_mcp.config.senado import SenadoSettings
from juris_bridge_mcp.config.server import ServerSettings
from juris_bridge_mcp.infrastructure.bootstrap import build_http_app

NOTICE = (
    "Juris Bridge MCP serves public Brazilian judicial data; "
    "use it responsibly and respect each Source's terms."
)


def main() -> None:
    """Start the server, refusing to run without a configured API key."""
    try:
        settings = ServerSettings()  # type: ignore[call-arg]  # values come from the environment
    except ValidationError:
        sys.exit("JURIS_BRIDGE_SERVER_API_KEYS must hold at least one API key; refusing to start.")
    print(NOTICE, flush=True)
    configure_logger()
    app = build_http_app(
        settings.keys(),
        LogSettings().environment(),
        datajud=DatajudSettings(),
        senado=SenadoSettings(),
        planalto=PlanaltoSettings(),
        legin=LeginSettings(),
        http=HttpSettings(),
    )
    # uvicorn's access log would add a second line per request next to the wide event.
    uvicorn.run(app, host=settings.host, port=settings.port, access_log=False)


if __name__ == "__main__":
    main()
