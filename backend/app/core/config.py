from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory (this file lives in backend/app/core/)
BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_SYSTEM_PROMPT = (
    "You are Aria, a helpful, friendly and concise AI assistant running locally on the user's computer. "
    "Answer clearly and accurately. Use Markdown for formatting and fenced code blocks for code. "
    "If you do not know something, say so instead of guessing."
)


class Config(BaseSettings):
    """Application configuration, loaded from environment variables and backend/.env."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Aria Local AI Voice Chatbot"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout: float = 120.0
    ollama_context_window: int = 4096
    history_limit: int = 20

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "aria_chatbot"
    mongodb_timeout_ms: int = 10000

    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    # Document uploads (the frontend shows the same 25 MB limit)
    max_upload_mb: int = 25
    max_concurrent_processing: int = 2
    uploads_dir: Path = BASE_DIR / "uploads"

    data_dir: Path = BASE_DIR / "data"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def runtime_settings_path(self) -> Path:
        return self.data_dir / "settings.json"


@lru_cache
def get_config() -> Config:
    return Config()
