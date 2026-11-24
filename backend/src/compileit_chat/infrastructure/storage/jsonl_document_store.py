"""Full page texts in one JSON-lines file.

The file doubles as the committed crawl snapshot: one page per line, sorted by URL and
UTF-8 (not \\u-escaped), so `git diff` after a re-crawl shows exactly what changed on the site.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from compileit_chat.domain.documents import Document, Language
from compileit_chat.domain.sources import normalize_url

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


class JsonlDocumentStore:
    """`DocumentStorePort` over a JSON Lines file (the committed snapshot), kept in memory after the
    first read.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._cache: dict[str, Document] | None = None

    async def replace_all(self, documents: Sequence[Document]) -> None:
        """Write the pages sorted by URL, so a re-crawl gives a small, readable git diff."""
        ordered = sorted(documents, key=lambda d: d.url)
        await asyncio.to_thread(self._write, ordered)
        self._cache = _index(ordered)

    async def get(self, url: str) -> Document | None:
        """Look up by URL, ignoring trailing slashes and host case."""
        return (await self._documents()).get(normalize_url(url))

    async def list_all(self) -> list[Document]:
        return list((await self._documents()).values())

    async def _documents(self) -> dict[str, Document]:
        if self._cache is None:
            self._cache = _index(await asyncio.to_thread(self._read))
        return self._cache

    def _read(self) -> list[Document]:
        if not self._path.exists():
            return []
        with self._path.open(encoding="utf-8") as file:
            return [_from_json(json.loads(line)) for line in file if line.strip()]

    def _write(self, documents: Sequence[Document]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as file:
            for document in documents:
                file.write(json.dumps(_to_json(document), ensure_ascii=False) + "\n")
        os.replace(temporary, self._path)  # atomic: readers never see a half-written file


def _index(documents: Sequence[Document]) -> dict[str, Document]:
    return {normalize_url(document.url): document for document in documents}


def _to_json(document: Document) -> dict[str, Any]:
    return {
        "url": document.url,
        "title": document.title,
        "lang": document.lang.value,
        "crawled_at": document.crawled_at.isoformat(),
        "text": document.text,
    }


def _from_json(data: dict[str, Any]) -> Document:
    return Document(
        url=data["url"],
        title=data["title"],
        text=data["text"],
        lang=Language(data["lang"]),
        crawled_at=datetime.fromisoformat(data["crawled_at"]),
    )
