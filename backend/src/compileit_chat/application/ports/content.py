"""Ports for getting website content in: crawl, extract, chunk."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from compileit_chat.domain.documents import Chunk, Document, FetchedPage


class WebCrawlerPort(Protocol):
    def crawl(self) -> AsyncIterator[FetchedPage]:
        """Yield every fetchable in-scope page once. Failed fetches are skipped, not raised."""
        ...


class ContentExtractorPort(Protocol):
    def extract(self, page: FetchedPage) -> Document | None:
        """Main content as markdown, or None if the page has no meaningful content."""
        ...


class ChunkerPort(Protocol):
    def split(self, document: Document) -> list[Chunk]: ...
