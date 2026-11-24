"""Chat model factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from pydantic import SecretStr


def openai_chat_model(
    model: str, api_key: SecretStr, temperature: float, timeout_seconds: float
) -> BaseChatModel:
    """The chat model: streaming, a few retries, and a per-request timeout."""
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        timeout=timeout_seconds,
        max_retries=2,
        streaming=True,
    )
