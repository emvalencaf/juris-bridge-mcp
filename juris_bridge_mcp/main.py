"""Entry point: reads settings, prints the notice and starts the server."""

import sys

import uvicorn
from pydantic import ValidationError

from juris_bridge_mcp.bootstrap import build_http_app
from juris_bridge_mcp.config.server import ServerSettings

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
    uvicorn.run(build_http_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
