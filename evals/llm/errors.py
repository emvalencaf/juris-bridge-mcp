"""Errors of the LLM client. None of them ever carries an API key."""


class LLMError(Exception):
    """Base of the errors raised by an LLM client."""


class RequestCapReached(LLMError):  # noqa: N818
    """The run reached its cap of requests; nothing more was sent."""


class AllKeysExhausted(LLMError):  # noqa: N818
    """Every configured key is out of daily quota; the run should stop and save its progress."""


class RateLimitRetriesExhausted(LLMError):  # noqa: N818
    """Every retry of a request met a 429 (or 503)."""


class GeminiAPIError(LLMError):
    """The Gemini API answered with a status that is not retryable.

    Attributes:
        status_code: The HTTP status (0 when no answer came).
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Gemini API answered {status_code}: {message}")
        self.status_code = status_code
