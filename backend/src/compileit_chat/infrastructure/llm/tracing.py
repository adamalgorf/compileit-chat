"""Optional LangSmith tracing.

LangChain/LangGraph read LangSmith settings from process environment variables. Settings
loaded from `.env` by pydantic-settings are not exported there, so they are set explicitly.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import SecretStr


def enable_langsmith(api_key: SecretStr, project: str) -> None:
    """Trace every graph run in LangSmith (optional, off by default)."""
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = api_key.get_secret_value()
    os.environ["LANGSMITH_PROJECT"] = project
