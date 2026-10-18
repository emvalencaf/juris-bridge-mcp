"""A `NormTextSource` that asks the Planalto first and Câmara Legin when the Planalto cannot."""

from dataclasses import replace

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation import Urn
from juris_bridge_mcp.domain.legislation_text import NormText
from juris_bridge_mcp.ports.norm_text_source import NormTextSource

# A changed page is the operator's to see, so only an unreachable Source falls back.
_FALLS_BACK_ON = frozenset(
    {ErrorCode.SOURCE_BLOCKED, ErrorCode.SOURCE_UNAVAILABLE, ErrorCode.RATE_LIMITED}
)


class FallbackNormTextSource:
    """Tries `primary`, then `fallback`; the fallback's text says why it was needed.

    Only a refusal, an outage or a rate limit of the primary falls back; `source_changed` and
    the like are raised, so a parser that stopped working is not hidden behind a warning.

    When the primary fails and the fallback has nothing or fails too, the primary's failure is
    raised, so a refusal is never hidden behind a missing page.
    """

    def __init__(self, primary: NormTextSource, fallback: NormTextSource) -> None:
        """Order the two Sources: `primary` is asked first."""
        self._primary = primary
        self._fallback = fallback

    async def fetch(self, urn: Urn) -> NormText | None:
        """Return the first text found, with a warning when it came from the fallback."""
        failure: ToolFailure | None = None
        try:
            found = await self._primary.fetch(urn)
        except ToolFailure as error:
            if error.code not in _FALLS_BACK_ON:
                raise
            found, failure = None, error
        if found is not None:
            return found
        try:
            text = await self._fallback.fetch(urn)
        except ToolFailure:
            if failure is not None:
                raise failure from None
            raise
        if text is None:
            if failure is not None:
                raise failure
            return None
        reason = (
            f"The Planalto failed ({failure.code.value})"
            if failure is not None
            else "The Planalto has no text page this server can locate for this norm"
        )
        return replace(
            text, warnings=(f"{reason}; the text comes from {text.source} instead.", *text.warnings)
        )
