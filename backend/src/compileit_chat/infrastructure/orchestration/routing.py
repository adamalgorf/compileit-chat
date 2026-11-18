"""Conditional routing after the model has spoken. Pure: state in, route name out."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from langchain_core.messages import AIMessage

if TYPE_CHECKING:
    from compileit_chat.infrastructure.orchestration.state import AgentState

type Route = Literal["tools", "fallback", "end"]


def should_continue(state: AgentState, max_tool_iterations: int) -> Route:
    """`tools` if the model asked for tools and has rounds left, `fallback` if it asked but
    the budget is spent, `end` when it produced a final answer."""
    last = state["messages"][-1]
    if not (isinstance(last, AIMessage) and last.tool_calls):
        return "end"
    if state["tool_iterations"] >= max_tool_iterations:
        return "fallback"
    return "tools"
