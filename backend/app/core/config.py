from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    frontend_url: str = "http://localhost:3000"
    database_url: str = (
        "postgresql+psycopg://knowledgepilot:knowledgepilot_local@localhost:5432/knowledgepilot"
    )
    redis_url: str = "redis://localhost:6379/0"
    session_days: int = 7
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    storage_backend: Literal["s3", "local"] = "s3"
    storage_local_path: str = "../.local/uploads"
    s3_endpoint: str | None = "http://localhost:9000"
    s3_bucket: str = "knowledgepilot"
    s3_access_key: str = "knowledgepilot_local"
    s3_secret_key: str = "knowledgepilot_local_secret"
    max_upload_bytes: int = 25 * 1024 * 1024
    chunk_target_tokens: int = 500
    chunk_max_tokens: int = 800
    chunk_overlap_tokens: int = 80
    rag_top_k: int = 8
    context_max_tokens: int = 6500
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    mail_from: str = "KnowledgePilot <noreply@knowledgepilot.local>"

    @model_validator(mode="after")
    def validate_invariants(self) -> "Settings":
        if self.embedding_dimensions != 1536:
            raise ValueError(
                "Schema v1 requires 1536 dimensions. Migrate and reindex before changing."
            )
        if not 0 <= self.chunk_overlap_tokens < self.chunk_target_tokens <= self.chunk_max_tokens:
            raise ValueError("Require overlap < target <= maximum chunk tokens")
        if self.app_env == "production":
            if not self.frontend_url.startswith("https://"):
                raise ValueError("Production requires HTTPS")
            if self.storage_backend != "s3" or "local" in self.s3_secret_key:
                raise ValueError(
                    "Production requires private S3 storage with configured credentials"
                )
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
