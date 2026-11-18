"""Managing the application's own secrets (stored encrypted, never in code)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from compileit_chat.application.ports import SecretStorePort

OPENAI_API_KEY = "openai_api_key"
KNOWN_SECRETS = frozenset({OPENAI_API_KEY})


class StoreSecret:
    def __init__(self, secrets: SecretStorePort) -> None:
        self._secrets = secrets

    async def execute(self, name: str, value: str) -> None:
        if name not in KNOWN_SECRETS:
            raise ValueError(f"Unknown secret {name!r}; known: {', '.join(sorted(KNOWN_SECRETS))}.")
        if not value.strip():
            raise ValueError("A secret cannot be empty.")
        await self._secrets.put(name, value.strip())
