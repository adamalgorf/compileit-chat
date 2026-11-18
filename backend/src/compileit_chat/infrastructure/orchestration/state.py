"""The state that flows through the orchestration graph and is checkpointed per session."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph import add_messages


class AgentState(TypedDict):
    # The whole conversation of the session; nodes append, `add_messages` merges.
    messages: Annotated[list[AnyMessage], add_messages]
    # Pages the tools returned during the current turn, as {"title", "url"} (plain data so
    # the checkpointer can store it). Reset at the start of every turn.
    sources: list[dict[str, str]]
    # Tool rounds used in the current turn; routing stops at the configured maximum.
    tool_iterations: int


def new_turn(question: str) -> AgentState:
    """Input for one turn: the new question appended, per-turn fields reset."""
    return {"messages": [HumanMessage(question)], "sources": [], "tool_iterations": 0}
