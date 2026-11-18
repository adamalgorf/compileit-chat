"""Every branch of `should_continue`."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from compileit_chat.infrastructure.orchestration.routing import Route, should_continue
from compileit_chat.infrastructure.orchestration.state import AgentState

ASKS_FOR_TOOL = AIMessage("", tool_calls=[{"name": "search_website", "args": {}, "id": "1"}])


def state(last: object, tool_iterations: int = 0) -> AgentState:
    return {
        "messages": [HumanMessage("Fråga"), last],
        "sources": [],
        "tool_iterations": tool_iterations,
    }  # type: ignore[list-item]


@pytest.mark.parametrize(
    ("last", "iterations", "expected"),
    [
        (ASKS_FOR_TOOL, 0, "tools"),
        (ASKS_FOR_TOOL, 2, "tools"),  # below the budget
        (ASKS_FOR_TOOL, 3, "fallback"),  # budget spent
        (ASKS_FOR_TOOL, 7, "fallback"),
        (AIMessage("Svar"), 0, "end"),  # final answer
        (AIMessage("Svar"), 3, "end"),  # an answer ends the turn even at the limit
        (ToolMessage("x", tool_call_id="1"), 0, "end"),  # defensive: not a model message
    ],
)
def test_should_continue(last: object, iterations: int, expected: Route) -> None:
    assert should_continue(state(last, iterations), max_tool_iterations=3) == expected
