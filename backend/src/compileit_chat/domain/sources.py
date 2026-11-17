"""Rules for citing sources: URL identity, de-duplication and picking what an answer cites."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

if TYPE_CHECKING:
    from collections.abc import Iterable

    from compileit_chat.domain.documents import SourceRef

_URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]\"']+")
_TRAILING_PUNCTUATION = ".,;:!?"


def normalize_url(url: str) -> str:
    """Canonical form used to compare URLs: lower-case host, no fragment, no trailing slash."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def unique_sources(sources: Iterable[SourceRef]) -> tuple[SourceRef, ...]:
    """Drop sources pointing at the same page, keeping the first occurrence and the order."""
    seen: set[str] = set()
    unique: list[SourceRef] = []
    for source in sources:
        key = normalize_url(source.url)
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return tuple(unique)


def cited_sources(answer: str, candidates: Iterable[SourceRef]) -> tuple[SourceRef, ...]:
    """Sources among `candidates` that the answer text actually links to.

    Showing only cited pages keeps the source list honest: retrieved-but-unused pages, and
    any sources at all for a "not found" answer, are left out.
    """
    linked = {
        normalize_url(url.rstrip(_TRAILING_PUNCTUATION)) for url in _URL_PATTERN.findall(answer)
    }
    return tuple(s for s in unique_sources(candidates) if normalize_url(s.url) in linked)
