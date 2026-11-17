"""Ports: the interfaces the application needs from the outside world.

Implemented by adapters in `infrastructure` and wired in `container.py`.
"""

from compileit_chat.application.ports.chat import ChatAgentPort, ConversationStorePort
from compileit_chat.application.ports.content import (
    ChunkerPort,
    ContentExtractorPort,
    WebCrawlerPort,
)
from compileit_chat.application.ports.knowledge import (
    DocumentStorePort,
    EmbeddingPort,
    RetrieverPort,
    VectorStorePort,
)

__all__ = [
    "ChatAgentPort",
    "ChunkerPort",
    "ContentExtractorPort",
    "ConversationStorePort",
    "DocumentStorePort",
    "EmbeddingPort",
    "RetrieverPort",
    "VectorStorePort",
    "WebCrawlerPort",
]
