"""Crawl the website and store the extracted pages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from compileit_chat.application.errors import IngestionError

if TYPE_CHECKING:
    from compileit_chat.application.ports import (
        ContentExtractorPort,
        DocumentStorePort,
        WebCrawlerPort,
    )
    from compileit_chat.domain.documents import Document

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestReport:
    pages_fetched: int
    documents: int
    skipped_empty: int
    skipped_duplicate: int


class IngestWebsite:
    """Crawl → extract → drop empty and duplicate pages → replace the stored documents."""

    def __init__(
        self,
        crawler: WebCrawlerPort,
        extractor: ContentExtractorPort,
        documents: DocumentStorePort,
    ) -> None:
        self._crawler = crawler
        self._extractor = extractor
        self._documents = documents

    async def execute(self) -> IngestReport:
        by_hash: dict[str, Document] = {}
        fetched = empty = duplicate = 0
        async for page in self._crawler.crawl():
            fetched += 1
            document = self._extractor.extract(page)
            if document is None:
                empty += 1
                logger.info("No main content: %s", page.url)
            elif (first := by_hash.get(document.content_hash)) is not None:
                duplicate += 1
                logger.info("Duplicate of %s: %s", first.url, document.url)
            else:
                by_hash[document.content_hash] = document

        if not by_hash:
            raise IngestionError("The crawl produced no documents; keeping the existing ones.")
        await self._documents.replace_all(list(by_hash.values()))
        return IngestReport(
            pages_fetched=fetched,
            documents=len(by_hash),
            skipped_empty=empty,
            skipped_duplicate=duplicate,
        )
