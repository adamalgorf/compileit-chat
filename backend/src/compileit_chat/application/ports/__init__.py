"""Ports: the interfaces the application needs from the outside world.

Implemented by adapters in `infrastructure` and wired in `container.py`.

Note the two conversation ports: `ConversationStorePort` is the *agent's* memory (what the
model remembers), `ConversationRepositoryPort` is the *saved history* users browse.
"""

from compileit_chat.application.ports.accounts import (
    AuthSessionStorePort,
    LoginEventLogPort,
    PasswordHasherPort,
    SecretStorePort,
    UserRepositoryPort,
)
from compileit_chat.application.ports.chat import ChatAgentPort, ConversationStorePort
from compileit_chat.application.ports.content import (
    ChunkerPort,
    ContentExtractorPort,
    WebCrawlerPort,
)
from compileit_chat.application.ports.history import (
    ApiCallLogPort,
    ClockPort,
    ConversationRepositoryPort,
)
from compileit_chat.application.ports.knowledge import (
    DocumentStorePort,
    EmbeddingPort,
    RetrieverPort,
    VectorStorePort,
)

__all__ = [
    "ApiCallLogPort",
    "AuthSessionStorePort",
    "ChatAgentPort",
    "ChunkerPort",
    "ClockPort",
    "ContentExtractorPort",
    "ConversationRepositoryPort",
    "ConversationStorePort",
    "DocumentStorePort",
    "EmbeddingPort",
    "LoginEventLogPort",
    "PasswordHasherPort",
    "RetrieverPort",
    "SecretStorePort",
    "UserRepositoryPort",
    "VectorStorePort",
    "WebCrawlerPort",
]
