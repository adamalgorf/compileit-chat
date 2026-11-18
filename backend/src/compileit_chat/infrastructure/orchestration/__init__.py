"""Agent orchestration: a hand-built LangGraph `StateGraph` behind `ChatAgentPort`.

state.py         what flows through the graph
graph.py         nodes, edges and conditional routing, compiled with a checkpointer
nodes.py         call_model, run_tools, collect_sources, handle_fallback
routing.py       should_continue: tools / fallback / end
tools.py         search_website, get_page, list_pages (thin wrappers over ports)
prompts.py       system prompt and untrusted-context delimiting
checkpointer.py  SQLite conversation store
orchestrator.py  runs the graph and maps its events to application events
"""
