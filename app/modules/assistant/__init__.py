"""
Assistant module.

A streaming agentic chat surface over the business's own records.

The agent is a LangGraph graph: the model reasons, calls read tools, sees the
results, and decides again before answering. LangGraph owns that loop; this
module owns everything the browser sees -- streaming transport, multi-tab
fan-out, cancellation and the persisted transcript.

Layout:

    models.py    threads, messages, runs
    services/    persistence, split by aggregate (thread, message, run)
    runtime.py   live runs -- queues, fan-out, cooperative cancellation
    agent.py     thread in, event stream out (drives the graph)
    graph.py     the LangGraph agent graph (model + tools loop)
    tools.py     the read-only capabilities the agent may call
    adapter.py   LangGraph's event stream -> our streaming contract
    events.py    the wire contract shared with the UI
    routers/     HTTP, split by resource; combined under /assistant
"""

from .routers import router

__all__ = ["router"]
