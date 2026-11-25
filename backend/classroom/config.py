"""Settings. Everything has a working default so `uvicorn classroom.api:app` runs with zero setup."""
from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["development", "production"] = "development"
    database_url: str = f"sqlite:///{ROOT / 'data' / 'classroom.db'}"
    secret_key: str = ""  # signs JWTs and derives the token-encryption key
    jwt_minutes: int = 60 * 12

    # Demo mode seeds a realistic classroom and enables one-click login as a teacher or student.
    demo_mode: bool = True

    # Google Classroom (optional). Create an OAuth client at console.cloud.google.com.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # Optional LLM to phrase answers. Retrieval and citations work without it.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    frontend_dir: Path = ROOT / "frontend" / "out"
    frontend_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.database_url.startswith("sqlite:///"):
        Path(s.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    if not s.secret_key:
        if s.env == "production":
            raise RuntimeError("SECRET_KEY must be set in production (python -c 'import secrets;print(secrets.token_urlsafe(48))')")
        s.secret_key = secrets.token_urlsafe(48)
        log.warning("SECRET_KEY not set: using a random key, so logins reset on restart.")
    if len(s.secret_key) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters")
    return s
