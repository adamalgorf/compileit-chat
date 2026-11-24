"""Keep generated sections of the docs (the orchestration graph) in sync with the code."""

from __future__ import annotations

import re

START_MARKER = "<!-- generated:orchestration-graph:start -->"
END_MARKER = "<!-- generated:orchestration-graph:end -->"
_BLOCK = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)


def render_block(mermaid: str) -> str:
    """The diagram wrapped in the markers that `make docs` replaces."""
    # Trailing whitespace is stripped so editors and pre-commit hooks cannot cause drift.
    body = "\n".join(line.rstrip() for line in mermaid.strip().splitlines())
    return f"{START_MARKER}\n```mermaid\n{body}\n```\n{END_MARKER}"


def with_diagram(document: str, mermaid: str) -> str:
    """The document with its generated block replaced by `mermaid`."""
    if not _BLOCK.search(document):
        raise ValueError(f"Markers {START_MARKER} ... {END_MARKER} not found.")
    return _BLOCK.sub(lambda _: render_block(mermaid), document)
