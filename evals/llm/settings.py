"""Settings of the LLM client, read from the environment and `.env` (never hard-coded)."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class EvalLLMSettings(BaseSettings):
    """Models, limits and keys for the agent, the judge and the calibration.

    The limits are per project and per model and Google changes them; copy them from
    the AI Studio rate-limit page. Variables are `EVALS_*`, except the keys, which are
    `GEMINI_API_KEY` and `GEMINI_API_KEYS`.
    """

    model_config = SettingsConfigDict(
        env_prefix="EVALS_", env_file=".env", extra="ignore", populate_by_name=True
    )

    agent_model: str
    judge_model: str
    calibration_model: str
    requests_per_minute: int = Field(gt=0)
    tokens_per_minute: int = Field(gt=0)
    requests_per_day: int = Field(gt=0)
    max_requests_per_run: int = Field(gt=0)
    rotate_keys: bool = False  # EVALS_ROTATE_KEYS; helps only across keys of different projects
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    timeout_seconds: float = 60.0
    max_retries: int = Field(default=6, ge=0)
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 60.0

    gemini_api_key: SecretStr | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_api_keys: SecretStr | None = Field(default=None, validation_alias="GEMINI_API_KEYS")

    @property
    def request_cap(self) -> int:
        """The most requests a run may send: the run cap, never above the daily quota."""
        return min(self.max_requests_per_run, self.requests_per_day)

    def api_keys(self) -> list[SecretStr]:
        """The keys given: `GEMINI_API_KEYS` (comma-separated) first, then `GEMINI_API_KEY`."""
        keys: list[SecretStr] = []
        if self.gemini_api_keys is not None:
            raw = self.gemini_api_keys.get_secret_value()
            keys.extend(SecretStr(part.strip()) for part in raw.split(",") if part.strip())
        if self.gemini_api_key is not None and self.gemini_api_key.get_secret_value():
            keys.append(self.gemini_api_key)
        return keys
