"""Turn a fetched page into a markdown `Document`: headings kept, site chrome removed.

Why not trafilatura alone? On compileit.com its article heuristics keep only one block of
card-based pages (e.g. 368 chars of /tjanster/ai) and drop headings on /kontakt. The site
does have a clean semantic `<main>`, so we render that directly and use trafilatura only as
a fallback for pages without one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import trafilatura
from lxml import html as lxml_html

from compileit_chat.domain.documents import Document, Language

if TYPE_CHECKING:
    from lxml.html import HtmlElement

    from compileit_chat.domain.documents import FetchedPage

# Removed inside <main>. `header`, `footer` and `button` are deliberately absent: within
# <main> they hold content (the page hero with the <h1>; accordion titles), and the site-wide
# header/footer live outside <main> anyway. Only block-level text is rendered, so bare button
# labels ("Skicka") never reach the output.
_CHROME_TAGS = frozenset(
    {"script", "style", "noscript", "template", "svg", "iframe", "form", "nav", "dialog"}
)
_HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_TEXT_BLOCKS = frozenset(
    {"p", "li", "blockquote", "address", "dt", "dd", "td", "th", "figcaption", "pre"}
)
_BLOCKS = _TEXT_BLOCKS | _HEADING_LEVELS.keys()
# Tags rendered without surrounding space; any other nested tag (div, br, ...) separates words.
_INLINE = frozenset(
    {"a", "span", "strong", "em", "b", "i", "u", "code", "small", "sup", "sub", "mark", "abbr"}
)
_CONTACT_LINK_PREFIXES = ("mailto:", "tel:")


class MainContentExtractor:
    def __init__(self, min_chars: int = 50) -> None:
        self._min_chars = min_chars

    def extract(self, page: FetchedPage) -> Document | None:
        tree = lxml_html.fromstring(page.html)
        main = tree.find(".//main")
        text = _render_main(main) if main is not None else _fallback(page.html)
        if len(text) < self._min_chars:
            return None
        return Document(
            url=page.url,
            title=_title(tree) or page.url,
            text=text,
            lang=_language(tree),
            crawled_at=page.fetched_at,
        )


def _render_main(main: HtmlElement) -> str:
    _strip_chrome(main)
    lines: list[str] = []
    seen: set[str] = set()  # responsive variants and carousels repeat the same blocks
    for element in main.iter():
        line = _render(element)
        if line and line.casefold() not in seen:
            seen.add(line.casefold())
            lines.append(line)
    return "\n\n".join(lines)


def _strip_chrome(root: HtmlElement) -> None:
    for element in list(root.iter()):
        if not isinstance(element.tag, str):  # comments, processing instructions
            continue
        hidden = element.get("aria-hidden") == "true" or element.get("hidden") is not None
        if element.tag in _CHROME_TAGS or hidden:
            element.drop_tree()  # keeps the tail text


def _render(element: HtmlElement) -> str | None:
    tag = element.tag
    if not isinstance(tag, str):
        return None
    if tag in _HEADING_LEVELS:
        text = _own_text(element)
        return f"{'#' * _HEADING_LEVELS[tag]} {text}" if text else None
    if tag in _TEXT_BLOCKS and not _has_block_descendant(element):
        text = _own_text(element)
        return f"- {text}" if text and _in_list_item(element) else text or None
    if tag == "a" and _is_contact_link(element) and not _has_block_ancestor(element):
        return _own_text(element) or None
    return None


def _own_text(element: HtmlElement) -> str:
    """Text of the element and its inline descendants; nested blocks are rendered separately."""
    parts = [element.text or ""]
    for child in element:
        if isinstance(child.tag, str) and child.tag not in _BLOCKS:
            separator = "" if child.tag in _INLINE else " "
            parts += [separator, _own_text(child), separator]
        parts.append(child.tail or "")
    return " ".join("".join(parts).split())


def _has_block_descendant(element: HtmlElement) -> bool:
    return any(d.tag in _BLOCKS for d in element.iterdescendants() if isinstance(d.tag, str))


def _has_block_ancestor(element: HtmlElement) -> bool:
    return any(a.tag in _BLOCKS for a in element.iterancestors())


def _in_list_item(element: HtmlElement) -> bool:
    if element.tag == "li":
        return True
    nearest_block = next((a for a in element.iterancestors() if a.tag in _BLOCKS), None)
    return nearest_block is not None and nearest_block.tag == "li"


def _is_contact_link(element: HtmlElement) -> bool:
    return (element.get("href") or "").startswith(_CONTACT_LINK_PREFIXES)


def _title(tree: HtmlElement) -> str | None:
    """`<title>` without the trailing " | Site name"; falls back to the first `<h1>`."""
    title = tree.findtext(".//title")
    if title and title.strip():
        segments = [s.strip() for s in title.split(" | ") if s.strip()]
        return " | ".join(segments[:-1] if len(segments) > 1 else segments)
    h1 = tree.find(".//h1")
    return (_own_text(h1) or None) if h1 is not None else None


def _language(tree: HtmlElement) -> Language:
    code = (tree.get("lang") or "").lower()
    if code.startswith("sv"):
        return Language.SWEDISH
    if code.startswith("en"):
        return Language.ENGLISH
    return Language.UNKNOWN


def _fallback(html: str) -> str:
    return trafilatura.extract(html, output_format="markdown", include_tables=True) or ""
