"""The graph's nodes. Each takes the state and returns the fields it updates."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from pydantic import ValidationError

from compileit_chat.infrastructure.orchestration.prompts import (
    FALLBACK_ANSWER,
    TOOL_CALL_CANCELLED,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langchain_core.language_models import LanguageModelInput
    from langchain_core.messages import BaseMessage, ToolCall
    from langchain_core.runnables import Runnable
    from langchain_core.tools import BaseTool

    from compileit_chat.infrastructure.orchestration.state import AgentState

logger = logging.getLogger(__name__)

type Update = dict[str, Any]


class AgentNodes:
    """Node functions bound to their dependencies (models, tools, prompt, history budget)."""

    def __init__(
        self,
        *,
        model: Runnable[LanguageModelInput, BaseMessage],
        grounding_model: Runnable[LanguageModelInput, BaseMessage],
        tools: Sequence[BaseTool],
        system_prompt: str,
        max_history_messages: int,
    ) -> None:
        self._model = model  # bound to the tools; may call them or answer
        self._grounding_model = grounding_model  # bound with tool_choice=search_website
        self._tools = {tool.name: tool for tool in tools}
        self._system_prompt = system_prompt
        self._max_history_messages = max_history_messages

    async def call_model(self, state: AgentState) -> Update:
        """Ask the model for the next step: tool calls or the final answer.

        The first step of every turn *must* search the website (`grounding_model`), so every
        answer, every "not found" and every refusal is backed by a search of the whole site,
        never only by memory or by one guessed page. Prompt instructions alone did not
        achieve this reliably in the eval (ADR-0007).
        The system prompt is added per call (never stored); earlier turns are trimmed.
        """
        model = self._grounding_model if state["tool_iterations"] == 0 else self._model
        history = close_unanswered_tool_calls(
            bounded_history(state["messages"], self._max_history_messages)
        )
        response = await model.ainvoke([SystemMessage(self._system_prompt), *history])
        return {"messages": [response]}

    async def run_tools(self, state: AgentState) -> Update:
        """Execute every tool call of the last model message, concurrently; count the round."""
        calls = _pending_tool_calls(state)
        results = await asyncio.gather(*(self._run_tool(call) for call in calls))
        return {"messages": list(results), "tool_iterations": state["tool_iterations"] + 1}

    async def collect_sources(self, state: AgentState) -> Update:
        """Add the pages the latest tool round returned to this turn's `sources`."""
        found = [
            source
            for message in _latest_tool_results(state["messages"])
            for source in (message.artifact or [])
        ]
        return {"sources": _unique_by_url([*state["sources"], *found])}

    async def handle_fallback(self, state: AgentState) -> Update:
        """Tool budget spent: close the open tool calls and give a polite fallback answer."""
        cancelled = [
            ToolMessage(TOOL_CALL_CANCELLED, tool_call_id=call["id"] or "", name=call["name"])
            for call in _pending_tool_calls(state)
        ]
        return {"messages": [*cancelled, AIMessage(FALLBACK_ANSWER)]}

    async def _run_tool(self, call: ToolCall) -> ToolMessage:
        """Run one tool call; a mistake the model can fix comes back as an error result."""
        tool = self._tools.get(call["name"])
        if tool is None:
            return _tool_error(call, f"Okänt verktyg: {call['name']}")
        try:
            result = await tool.ainvoke({**call, "type": "tool_call"})
        except ValidationError as error:
            # Bad arguments are the model's mistake: report back so it can retry. Anything
            # else (e.g. the embeddings API is down) propagates and fails the turn.
            return _tool_error(call, f"Ogiltiga argument: {error.errors()}")
        if not isinstance(result, ToolMessage):  # pragma: no cover - guaranteed by tool_call input
            raise TypeError(f"Tool {call['name']} returned {type(result).__name__}")
        return result


def bounded_history(messages: Sequence[BaseMessage], max_earlier: int) -> list[BaseMessage]:
    """The current turn in full, plus at most `max_earlier` messages of earlier turns.

    Earlier turns are cut at a user message, so the model never sees a tool result without
    the call that produced it. The full history stays in the checkpoint.
    """
    current_start = max(
        (i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=0
    )
    earlier = trim_messages(
        list(messages[:current_start]),
        max_tokens=max_earlier,
        token_counter=len,  # one "token" per message
        strategy="last",
        start_on="human",
    )
    return [*earlier, *messages[current_start:]]


def close_unanswered_tool_calls(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """Answer tool calls that never got a result, as "cancelled", right after their message.

    A user who presses stop while a tool runs leaves a checkpoint whose last model message
    has tool calls but no results. The provider rejects such a history, which would break the
    session for good, so the model input is repaired here. The checkpoint stays as it was.
    """
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    repaired: list[BaseMessage] = []
    for message in messages:
        repaired.append(message)
        if isinstance(message, AIMessage):
            repaired += [
                ToolMessage(TOOL_CALL_CANCELLED, tool_call_id=call["id"] or "", name=call["name"])
                for call in message.tool_calls
                if call["id"] not in answered
            ]
    return repaired


def _pending_tool_calls(state: AgentState) -> list[ToolCall]:
    """The tool calls the model just asked for (empty if it answered instead)."""
    last = state["messages"][-1]
    return list(last.tool_calls) if isinstance(last, AIMessage) else []


def _latest_tool_results(messages: Sequence[BaseMessage]) -> list[ToolMessage]:
    """The tool results at the end of the history, i.e. those of the round that just ran."""
    results: list[ToolMessage] = []
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            break
        results.insert(0, message)
    return results


def _unique_by_url(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop repeated pages, keeping each at the position it was first found."""
    return list({source["url"]: source for source in reversed(sources)}.values())[::-1]


def _tool_error(call: ToolCall, content: str) -> ToolMessage:
    return ToolMessage(content, tool_call_id=call["id"] or "", name=call["name"], status="error")
