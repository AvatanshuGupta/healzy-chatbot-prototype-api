"""
config.py
=========
Centralized configuration for the whole app.

WHY THIS FILE EXISTS:
Instead of scattering `os.getenv(...)` calls everywhere, we load all
environment variables ONCE here, validate their types using Pydantic,
and expose a single `settings` object that every other file imports.

This makes the app:
  - Easier to test (you can override `settings` in tests)
  - Easier to debug (one place to look for config)
  - Safer (Pydantic will error loudly at startup if something required
    is missing, instead of failing weirdly deep inside a request)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- Supabase ----
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # ---- Hugging Face ----
    HF_TOKEN: str
    HF_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"

    # ---- LLM generation params ----
    LLM_MAX_NEW_TOKENS: int = 512
    LLM_TEMPERATURE: float = 0.6

    # ---- Context window sizes ----
    CHAT_HISTORY_WINDOW: int = 12       # how many past messages to include
    CHECKIN_HISTORY_WINDOW: int = 14    # how many past checkins to include

    # ---- CORS ----
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Tells pydantic-settings to load variables from a ".env" file
    # located in the project root, in addition to real environment vars.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins_list(self) -> list[str]:
        """Convert the comma-separated ALLOWED_ORIGINS string into a list
        for FastAPI's CORS middleware."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


# A single, shared instance imported by every other module.
# Example usage elsewhere: `from app.config import settings`
settings = Settings()
