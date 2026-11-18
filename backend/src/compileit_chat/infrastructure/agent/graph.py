"""The agent graph: a tool-calling loop written out as an explicit LangGraph `StateGraph`.

    START -> agent --(tool calls?)--> tools -> agent -> ... -> END

Built by hand rather than with `create_react_agent` so the three things we care about are
visible in one place: the system prompt is injected per call (never stored in history),
older turns are trimmed before the model sees them, and the loop is bounded by the
recursion limit the adapter passes in. See ADR-0002.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage, trim_messages
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import BaseMessage
    from langchain_core.tools import BaseTool
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

AGENT_NODE = "agent"
TOOLS_NODE = "tools"


def build_agent_graph(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    system_prompt: str,
    checkpointer: BaseCheckpointSaver[str],
    max_history_messages: int,
) -> CompiledStateGraph[MessagesState]:
    model_with_tools = model.bind_tools(tools)

    async def call_model(state: MessagesState) -> MessagesState:
        messages = bounded_history(state["messages"], max_history_messages)
        response = await model_with_tools.ainvoke([SystemMessage(system_prompt), *messages])
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node(AGENT_NODE, call_model)
    builder.add_node(TOOLS_NODE, ToolNode(tools))
    builder.add_edge(START, AGENT_NODE)
    builder.add_conditional_edges(AGENT_NODE, tools_condition)
    builder.add_edge(TOOLS_NODE, AGENT_NODE)
    return builder.compile(checkpointer=checkpointer)


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
