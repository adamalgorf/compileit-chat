"""Heading-aware chunking of markdown documents.

Paragraphs are packed greedily into chunks of at most `max_tokens`. Once a chunk has reached
`target_tokens`, the next heading starts a new chunk, so chunks tend to align with sections.
Paragraphs larger than `max_tokens` are split by sentence (then by word). When a chunk is
cut mid-section, its last paragraphs (up to `overlap_tokens`) are repeated in the next one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import tiktoken

from compileit_chat.domain.documents import Chunk

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from compileit_chat.domain.documents import Document

type TokenCounter = Callable[[str], int]

_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def tiktoken_counter(encoding_name: str = "cl100k_base") -> TokenCounter:
    """Token counter matching OpenAI's embedding models (cl100k_base)."""
    encoding = tiktoken.get_encoding(encoding_name)
    return lambda text: len(encoding.encode(text))


@dataclass(frozen=True, slots=True)
class _Block:
    text: str
    headings: tuple[str, ...]  # heading path in effect; for a heading block, ends with itself
    is_heading: bool
    tokens: int


class HeadingAwareChunker:
    """`ChunkerPort` adapter: splits pages at headings into chunks of about `target_tokens`, never
    more than `max_tokens`.
    """

    def __init__(
        self,
        count_tokens: TokenCounter,
        target_tokens: int = 500,
        max_tokens: int = 800,
        overlap_tokens: int = 80,
    ) -> None:
        if not 0 < target_tokens <= max_tokens:
            raise ValueError("Require 0 < target_tokens <= max_tokens.")
        if not 0 <= overlap_tokens < target_tokens:
            raise ValueError("Require 0 <= overlap_tokens < target_tokens.")
        self._count = count_tokens
        self._target = target_tokens
        self._max = max_tokens
        self._overlap = overlap_tokens

    def split(self, document: Document) -> list[Chunk]:
        """Each chunk keeps the page's metadata and its section heading."""
        groups = self._pack(list(self._blocks(document.text)))
        return [
            Chunk(
                document_url=document.url,
                title=document.title,
                section_heading=_section_heading(group),
                text="\n\n".join(block.text for block in group),
                lang=document.lang,
                crawled_at=document.crawled_at,
                position=position,
            )
            for position, group in enumerate(groups)
        ]

    def _blocks(self, markdown: str) -> Iterator[_Block]:
        stack: list[tuple[int, str]] = []  # (level, heading text)
        for paragraph in (p.strip() for p in markdown.split("\n\n")):
            if not paragraph:
                continue
            if match := _HEADING.match(paragraph):
                level, text = len(match[1]), match[2].strip()
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, text))
                path = tuple(heading for _, heading in stack)
                yield _Block(paragraph, path, is_heading=True, tokens=self._count(paragraph))
                continue
            path = tuple(heading for _, heading in stack)
            for piece in self._fit(paragraph):
                yield _Block(piece, path, is_heading=False, tokens=self._count(piece))

    def _fit(self, text: str) -> list[str]:
        """Split text into pieces of at most `max_tokens`: by sentence, then by word."""
        if self._count(text) <= self._max:
            return [text]
        sentences = _SENTENCE_END.split(text)
        units = sentences if len(sentences) > 1 else text.split()
        pieces: list[str] = []
        current = ""
        for unit in units:
            candidate = f"{current} {unit}".strip()
            if current and self._count(candidate) > self._max:
                pieces.append(current)
                current = unit
            else:
                current = candidate
        pieces.append(current)
        return (
            [piece for part in pieces for piece in self._fit(part)] if len(pieces) > 1 else pieces
        )

    def _pack(self, blocks: list[_Block]) -> list[list[_Block]]:
        groups: list[list[_Block]] = []
        current: list[_Block] = []
        for block in blocks:
            size = sum(b.tokens for b in current)
            too_big = size + block.tokens > self._max
            section_break = block.is_heading and size >= self._target
            if current and (too_big or section_break):
                headings = _trailing_headings(current)
                body = current[: len(current) - len(headings)]
                groups.append(body)
                carry_over = [] if block.is_heading or headings else self._overlap_tail(body)
                if sum(b.tokens for b in carry_over) + block.tokens > self._max:
                    carry_over = []
                current = carry_over + headings
            current.append(block)
        groups.append(current)
        return [group for group in groups if any(not b.is_heading for b in group)]

    def _overlap_tail(self, blocks: list[_Block]) -> list[_Block]:
        tail: list[_Block] = []
        for block in reversed(blocks):
            if block.is_heading or sum(b.tokens for b in tail) + block.tokens > self._overlap:
                break
            tail.insert(0, block)
        return tail


def _trailing_headings(blocks: list[_Block]) -> list[_Block]:
    """Headings at the end of a group belong with the content that follows them."""
    count = 0
    for block in reversed(blocks):
        if not block.is_heading:
            break
        count += 1
    return blocks[len(blocks) - count :]


def _section_heading(group: list[_Block]) -> str | None:
    first_content = next(block for block in group if not block.is_heading)
    return " > ".join(first_content.headings) or None
