"""The orchestration graph, wired by hand (no prebuilt agent):

    START → call_model ──(tool calls)──────► run_tools → collect_sources → call_model
                       ├─(tool budget spent)─► handle_fallback → END
                       └─(final answer)──────► END

`docs/architecture.md` embeds the diagram generated from this code (`make docs`).
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from compileit_chat.infrastructure.orchestration.nodes import AgentNodes
from compileit_chat.infrastructure.orchestration.routing import should_continue
from compileit_chat.infrastructure.orchestration.state import AgentState

if TYPE_CHECKING:
    from langchain_core.language_models import LanguageModelInput
    from langchain_core.messages import BaseMessage
    from langchain_core.runnables import Runnable
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

CALL_MODEL = "call_model"
RUN_TOOLS = "run_tools"
COLLECT_SOURCES = "collect_sources"
HANDLE_FALLBACK = "handle_fallback"


def build_graph(
    nodes: AgentNodes,
    max_tool_iterations: int,
    checkpointer: BaseCheckpointSaver[str] | None = None,
) -> CompiledStateGraph[AgentState]:
    """Wire the nodes into the graph above and compile it.

    The only branching point is after `call_model`; `should_continue` decides between
    running tools, falling back (tool budget spent) and ending with the model's answer.
    With a checkpointer, the state is saved after every step under the session's thread id,
    which is what makes follow-up questions work.
    """
    builder = StateGraph(AgentState)
    builder.add_node(CALL_MODEL, nodes.call_model)
    builder.add_node(RUN_TOOLS, nodes.run_tools)
    builder.add_node(COLLECT_SOURCES, nodes.collect_sources)
    builder.add_node(HANDLE_FALLBACK, nodes.handle_fallback)

    builder.add_edge(START, CALL_MODEL)
    # The route names returned by `should_continue` map to the next node.
    builder.add_conditional_edges(
        CALL_MODEL,
        partial(should_continue, max_tool_iterations=max_tool_iterations),
        {"tools": RUN_TOOLS, "fallback": HANDLE_FALLBACK, "end": END},
    )
    # After tools: record their sources, then let the model read the results (the loop).
    builder.add_edge(RUN_TOOLS, COLLECT_SOURCES)
    builder.add_edge(COLLECT_SOURCES, CALL_MODEL)
    builder.add_edge(HANDLE_FALLBACK, END)
    return builder.compile(checkpointer=checkpointer)


def recursion_limit(max_tool_iterations: int) -> int:
    """LangGraph's hard step cap, derived from the graph's shape: a backstop behind routing.

    The longest legitimate turn is 3 steps per tool round (call_model, run_tools,
    collect_sources), then call_model and handle_fallback. LangGraph raises when the step
    count *reaches* the limit, so allow one more.
    """
    return 3 * max_tool_iterations + 3


def mermaid_diagram(max_tool_iterations: int = 4) -> str:
    """The graph as Mermaid, for the docs. Node functions are never invoked."""
    # Drawing only needs the structure, so the models are stand-ins and no API key is needed.
    placeholder: Runnable[LanguageModelInput, BaseMessage] = RunnableLambda(lambda _: AIMessage(""))
    nodes = AgentNodes(
        model=placeholder,
        grounding_model=placeholder,
        tools=[],
        system_prompt="",
        max_history_messages=0,
    )
    return build_graph(nodes, max_tool_iterations).get_graph().draw_mermaid()
