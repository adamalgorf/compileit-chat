"""All runtime configuration, read from the environment (and `.env`). Only read by the container."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    embedding_model: str = "text-embedding-3-small"

    # Crawling. Profiles under /medarbetare/<id> are thin personal pages that add retrieval
    # noise; leadership and contact details are on /kontakt.
    site_url: str = "https://compileit.com"
    crawl_user_agent: str = "compileit-chat-case/0.1 (educational crawler)"
    crawl_max_pages: int = Field(default=200, gt=0)
    crawl_max_depth: int = Field(default=3, ge=0)
    crawl_concurrency: int = Field(default=4, gt=0)
    crawl_timeout_seconds: float = Field(default=15.0, gt=0)
    crawl_exclude_patterns: list[str] = [r"^/medarbetare/.+"]

    # Chunking (tokens, as counted by the embedding model's tokenizer)
    chunk_target_tokens: int = Field(default=500, gt=0)
    chunk_max_tokens: int = Field(default=800, gt=0)
    chunk_overlap_tokens: int = Field(default=80, ge=0)

    # Hybrid retrieval: candidates fetched from each retriever before rank fusion
    retrieval_candidates: int = Field(default=20, gt=0)
    rrf_k: int = Field(default=60, gt=0)

    # Storage. The snapshot is committed; runtime state is git-ignored.
    data_dir: Path = BACKEND_DIR / "data"

    @property
    def snapshot_path(self) -> Path:
        return self.data_dir / "snapshot" / "pages.jsonl"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "runtime" / "chroma"
