"""Shared base for the per-concern settings classes."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    """Settings read only from the environment; subclasses set their own prefix."""

    model_config = SettingsConfigDict(extra="ignore")
