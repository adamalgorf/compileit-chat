"""The agent's tools: thin wrappers that call ports and format the result.

Each tool returns (content, artifact):
- content: text for the model, with site content delimited as untrusted data (prompts.py);
- artifact: the pages involved as `{"title", "url"}` dicts. The `collect_sources` node
  gathers them into the graph state.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from compileit_chat.infrastructure.orchestration.prompts import pages_block, source_block

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from langchain_core.tools import BaseTool

    from compileit_chat.application.ports import DocumentStorePort, RetrieverPort
    from compileit_chat.domain.documents import Document, SourceRef

type ToolResult = tuple[str, list[dict[str, str]]]

# Every turn starts with this tool (see `AgentNodes.call_model`).
SEARCH_TOOL = "search_website"

_TRANSLITERATION = str.maketrans("åäö", "aao")


# Argument schemas. The model reads the field descriptions, so they are in Swedish and say
# how to phrase good arguments; Pydantic rejects bad ones before the tool runs.


class SearchWebsiteArgs(BaseModel):
    query: str = Field(
        description=(
            "Fristående sökfråga på svenska med konkreta nyckelord, t.ex. 'AI-tjänster' "
            "eller 'kontor adress'. Skriv om följdfrågor till det ämne de syftar på."
        ),
        min_length=1,
        max_length=300,
    )
    k: int = Field(default=5, ge=1, le=8, description="Antal textavsnitt att hämta.")


class GetPageArgs(BaseModel):
    url_or_title: str = Field(
        description=(
            "Sidans URL (https://compileit.com/om-oss), sökväg (/om-oss) eller titel (Om oss)."
        ),
        min_length=1,
        max_length=300,
    )


class ListPagesArgs(BaseModel):
    pass


def build_tools(
    retriever: RetrieverPort,
    documents: DocumentStorePort,
    max_page_chars: int = 12_000,
) -> list[BaseTool]:
    """The three tools, bound to the ports they read from.

    The tool descriptions are prompts too: they tell the model when to use which tool.
    """

    async def search_website(query: str, k: int = 5) -> ToolResult:
        """Hybrid search; each hit is returned as a delimited block with its source."""
        hits = await retriever.search(query, k)
        if not hits:
            return f"Inga träffar för '{query}'.", []
        blocks = [
            source_block(h.chunk.source, h.chunk.text, section=h.chunk.section_heading)
            for h in hits
        ]
        return "\n\n".join(blocks), _artifact(h.chunk.source for h in hits)

    async def get_page(url_or_title: str) -> ToolResult:
        """A whole page, for summaries; capped so one long page cannot fill the context."""
        document = find_page(await documents.list_all(), url_or_title)
        if document is None:
            return (
                f"Ingen sida matchar '{url_or_title}'. Använd list_pages för att se vilka "
                "sidor som finns.",
                [],
            )
        text = document.text
        if len(text) > max_page_chars:
            text = text[:max_page_chars] + "\n\n[Sidan är avkortad.]"
        return source_block(document.source, text), _artifact([document.source])

    async def list_pages() -> ToolResult:
        """Every page's title and URL, so the model can pick one for `get_page`."""
        pages = sorted(await documents.list_all(), key=lambda d: d.url)
        return pages_block(d.source for d in pages), _artifact(d.source for d in pages)

    return [
        StructuredTool.from_function(
            coroutine=search_website,
            name=SEARCH_TOOL,
            description=(
                "Sök i innehållet på compileit.com (hybrid semantisk + nyckelordssökning). "
                "Returnerar de mest relevanta textavsnitten med titel och URL."
            ),
            args_schema=SearchWebsiteArgs,
            response_format="content_and_artifact",
        ),
        StructuredTool.from_function(
            coroutine=get_page,
            name="get_page",
            description=(
                "Hämta hela texten för en sida på compileit.com, t.ex. för att sammanfatta "
                "den eller länka den som källa. Nyckelsidor: /uppdrag listar Compileits kunder "
                "och uppdrag (använd den för frågor om kunder och branscher), /vara-tjanster "
                "tjänsterna, /kontakt kontaktuppgifter och kontor, /om-oss företaget."
            ),
            args_schema=GetPageArgs,
            response_format="content_and_artifact",
        ),
        StructuredTool.from_function(
            coroutine=list_pages,
            name="list_pages",
            description="Lista alla sidor på compileit.com (titel och URL).",
            args_schema=ListPagesArgs,
            response_format="content_and_artifact",
        ),
    ]


def find_page(documents: Sequence[Document], url_or_title: str) -> Document | None:
    """Resolve a URL, a path or a title to a page, most specific match first."""
    target = url_or_title.strip()
    if target.startswith(("http://", "https://", "/")):
        wanted = _path_key(target)
        return next((d for d in documents if _path_key(d.url) == wanted), None)

    folded, slug = target.casefold(), _slug(target)
    checks = (
        lambda d: d.title.casefold() == folded,
        lambda d: _path_key(d.url).rsplit("/", 1)[-1] == slug,  # "Om oss" -> /om-oss
        lambda d: folded in d.title.casefold(),
    )
    for check in checks:
        if match := next((d for d in documents if check(d)), None):
            return match
    return None


def _artifact(sources: Iterable[SourceRef]) -> list[dict[str, str]]:
    """Sources as plain dicts, so the checkpointer can store them in the graph state."""
    return [{"title": s.title, "url": s.url} for s in sources]


def _path_key(url: str) -> str:
    """Compare pages by path only, so www/non-www, trailing slashes and case don't matter."""
    return urlsplit(url).path.rstrip("/").casefold()


def _slug(text: str) -> str:
    """A title as a URL slug: "Våra tjänster" -> "vara-tjanster"."""
    return re.sub(r"[^a-z0-9]+", "-", text.casefold().translate(_TRANSLITERATION)).strip("-")
