"""docs/architecture.md must show the orchestration graph the code actually builds."""

import pytest

from compileit_chat.infrastructure.orchestration.graph import mermaid_diagram
from compileit_chat.interface.cli.generated_docs import END_MARKER, START_MARKER, with_diagram
from compileit_chat.interface.cli.main import ARCHITECTURE_DOC


def test_architecture_doc_matches_the_graph_in_code() -> None:
    document = ARCHITECTURE_DOC.read_text(encoding="utf-8")

    assert with_diagram(document, mermaid_diagram()) == document, "Run `make docs`."


def test_with_diagram_replaces_only_the_generated_block() -> None:
    document = f"# Title\n\n{START_MARKER}\nold\n{END_MARKER}\n\nAfter."

    updated = with_diagram(document, "graph TD;  \n\tA --> B;\n")

    assert updated == (
        f"# Title\n\n{START_MARKER}\n```mermaid\ngraph TD;\n\tA --> B;\n```\n{END_MARKER}\n\nAfter."
    )


def test_with_diagram_requires_markers() -> None:
    with pytest.raises(ValueError, match="Markers"):
        with_diagram("# No markers", "graph TD;")
