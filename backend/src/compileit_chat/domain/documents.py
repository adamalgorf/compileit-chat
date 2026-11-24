"""Website content as the domain sees it: fetched pages, documents, chunks and their sources."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class Language(StrEnum):
    """A page's language, read from its HTML `lang` attribute."""

    SWEDISH = "sv"
    ENGLISH = "en"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SourceRef:
    """A citable web page."""

    title: str
    url: str


@dataclass(frozen=True, slots=True)
class FetchedPage:
    """A raw HTTP result from the crawler, before content extraction."""

    url: str
    html: str
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class Document:
    """The main textual content of one web page, as markdown with headings preserved."""

    url: str
    title: str
    text: str
    lang: Language
    crawled_at: datetime

    @property
    def source(self) -> SourceRef:
        """This page as a citation."""
        return SourceRef(title=self.title, url=self.url)

    @property
    def content_hash(self) -> str:
        """Hash of the whitespace- and case-normalised text, used to drop duplicate pages."""
        normalised = " ".join(self.text.split()).casefold()
        return hashlib.sha256(normalised.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable slice of a document, carrying everything needed to cite it."""

    document_url: str
    title: str
    section_heading: str | None
    text: str
    lang: Language
    crawled_at: datetime
    position: int

    @property
    def id(self) -> str:
        """Deterministic id, so re-ingesting the same page overwrites instead of duplicating."""
        url_hash = hashlib.sha256(self.document_url.encode()).hexdigest()[:16]
        return f"{url_hash}-{self.position:04d}"

    @property
    def source(self) -> SourceRef:
        """The page this chunk comes from, as a citation."""
        return SourceRef(title=self.title, url=self.document_url)

    @property
    def search_text(self) -> str:
        """Text to index: the chunk prefixed with its page title and section.

        A chunk like "Vi finns i tre städer" is only findable for "kontor" if it carries
        the context that it sits under "Kontakta oss > Våra kontor".
        """
        context = " > ".join(part for part in (self.title, self.section_heading) if part)
        return f"{context}\n\n{self.text}"


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    """A retrieval hit. Higher score means more relevant; the scale is retriever-specific."""

    chunk: Chunk
    score: float
