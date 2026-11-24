"""All runtime configuration, read from the environment (and `.env`). Only read by the container."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All configuration, read from environment variables or `.env`. Each field maps to the upper-
    case variable of the same name (`openai_api_key` -> `OPENAI_API_KEY`).
    """

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    embedding_model: str = "text-embedding-3-small"
    # Fast, cheap, reliable at tool calling, and accepts a low temperature (GPT-5-family
    # reasoning models ignore temperature and add latency).
    chat_model: str = "gpt-4.1-mini"
    chat_temperature: float = Field(default=0.1, ge=0, le=2)
    llm_timeout_seconds: float = Field(default=30.0, gt=0)

    # Agent guard rails
    agent_max_tool_iterations: int = Field(default=4, gt=0)  # tool rounds, then fallback
    agent_timeout_seconds: float = Field(default=60.0, gt=0)
    history_max_messages: int = Field(default=20, gt=0)  # earlier-turn messages sent to model

    # HTTP API
    api_cors_origins: list[str] = ["http://localhost:3000"]
    api_rate_limit_requests: int = Field(default=20, gt=0)  # chat requests per client...
    api_rate_limit_window_seconds: float = Field(default=60.0, gt=0)  # ...per window
    log_level: str = "INFO"

    # Database (users, login sessions and events, chat history, API call log, secrets).
    # Unset: a SQLite file under data/runtime. Any SQLAlchemy async URL works, e.g.
    # postgresql+asyncpg://user:pass@host/db (install the driver).
    database_url: str | None = None
    # Encrypts secrets stored in the database (Fernet key). Never in code or the database.
    secrets_master_key: SecretStr | None = None

    # Login
    auth_session_hours: int = Field(default=12, gt=0)
    auth_cookie_secure: bool = False  # set true behind HTTPS

    # Optional LangSmith tracing of every agent run (model calls, tool calls, graph steps)
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "compileit-chat"

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

    # Hybrid retrieval: hits from each side before rank fusion (tuned in ADR-0003)
    retrieval_vector_candidates: int = Field(default=20, gt=0)
    retrieval_lexical_candidates: int = Field(default=3, ge=0)
    rrf_k: int = Field(default=60, gt=0)

    # Storage. The snapshot is committed; runtime state is git-ignored.
    data_dir: Path = BACKEND_DIR / "data"

    @property
    def snapshot_path(self) -> Path:
        """The crawled pages; committed to git (ADR-0004)."""
        return self.data_dir / "snapshot" / "pages.jsonl"

    @property
    def chroma_dir(self) -> Path:
        """The vector index; rebuilt from the snapshot, not committed."""
        return self.data_dir / "runtime" / "chroma"

    @property
    def effective_database_url(self) -> str:
        """`DATABASE_URL` if set, else a SQLite file."""
        default = self.data_dir / "runtime" / "app.sqlite3"
        return self.database_url or f"sqlite+aiosqlite:///{default.as_posix()}"

    @property
    def checkpoint_db(self) -> Path:
        """LangGraph's checkpoints: the agent's conversation memory."""
        return self.data_dir / "runtime" / "checkpoints.sqlite3"
