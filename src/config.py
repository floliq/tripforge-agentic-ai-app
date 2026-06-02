import os

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TRIPFORGE_",
        extra="ignore",
    )

    ollama_base_url: str = os.getenv("TRIPFORGE_OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("TRIPFORGE_OLLAMA_MODEL", "qwen3:32b")
    ollama_embed_model: str = os.getenv("TRIPFORGE_OLLAMA_EMBED_MODEL", "nomic-embed-text")
    chroma_dir: Path = Path("./data/chroma")
    artifacts_dir: Path = Path("./data/artifacts")
    opentripmap_api_key: str | None = os.getenv("TRIPFORGE_OPENTRIPMAP_API_KEY", None)
    openrouteservice_api_key: str | None = os.getenv("TRIPFORGE_OPENROUTER_API_KEY", None)
    request_timeout_seconds: int = Field(default=60, ge=1, le=120)
    max_places: int = Field(default=10, ge=1, le=50)
    max_hotels: int = Field(default=8, ge=1, le=30)
    langfuse_base_url: str = os.getenv(
        "TRIPFORGE_LANGFUSE_BASE_URL", "https://cloud.langfuse.com"
    )
    langfuse_public_key: str | None = os.getenv("TRIPFORGE_LANGFUSE_PUBLIC_KEY", None)
    langfuse_secret_key: str | None = os.getenv("TRIPFORGE_LANGFUSE_SECRET_KEY", None)
