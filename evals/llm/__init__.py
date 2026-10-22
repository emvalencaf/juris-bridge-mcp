"""The narrow client the agent and the judge use to reach a language model."""

from evals.llm.client import (
    ChatResult,
    LLMClient,
    Message,
    ToolCall,
    ToolDeclaration,
    Usage,
)
from evals.llm.errors import (
    AllKeysExhausted,
    GeminiAPIError,
    LLMError,
    RateLimitRetriesExhausted,
    RequestCapReached,
)
from evals.llm.fakes import FakeClock, ScriptedLLMClient
from evals.llm.gemini import GeminiClient
from evals.llm.keys import ApiKey, KeySource, RotatingKeySource, SingleKeySource, key_source_from
from evals.llm.limits import RateLimiter, RequestBudget
from evals.llm.settings import EvalLLMSettings

__all__ = [
    "AllKeysExhausted",
    "ApiKey",
    "ChatResult",
    "EvalLLMSettings",
    "FakeClock",
    "GeminiAPIError",
    "GeminiClient",
    "KeySource",
    "LLMClient",
    "LLMError",
    "Message",
    "RateLimitRetriesExhausted",
    "RateLimiter",
    "RequestBudget",
    "RequestCapReached",
    "RotatingKeySource",
    "ScriptedLLMClient",
    "SingleKeySource",
    "ToolCall",
    "ToolDeclaration",
    "Usage",
    "key_source_from",
]
