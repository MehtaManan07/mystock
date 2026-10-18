"""
Assistant module.

A streaming agentic chat surface over the business's own records.

Everything here is production code with one exception: ``llm.py``, which
streams scripted text instead of calling a model. Swapping in a real provider
is a change to that file alone.

Layout:

    models.py    threads, messages, runs
    services/    persistence, split by aggregate (thread, message, run)
    runtime.py   live runs -- queues, fan-out, cooperative cancellation
    agent.py     thread in, event stream out
    llm.py       the model call (stubbed)
    events.py    the wire contract shared with the UI
    routers/     HTTP, split by resource; combined under /assistant
"""

from .routers import router

__all__ = ["router"]
