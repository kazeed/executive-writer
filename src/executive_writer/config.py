"""Validated environment configuration; no implicit .env loading."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EW_", extra="ignore", hide_input_in_errors=True)

    environment: Literal["development", "production"] = "development"
    docs_enabled: bool = True
