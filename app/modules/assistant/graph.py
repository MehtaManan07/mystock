"""
The agent graph.

This is the loop the whole rebuild is for. The old agent was a straight line --
history in, tokens out -- so it could only ever talk, never look anything up.
A graph gives it the one thing it was missing: the ability to *act, see the
result, and decide again*.

THE SHAPE
---------
Two nodes and one decision::

        START → model → (tool_calls?) → tools → model → ... → END
                   └────────── no tool_calls ──────────→ END

The ``model`` node asks the LLM what to do next. If it asked to call tools, the
``tools`` node runs them and loops back so the model can read the results;
otherwise the model has produced its final answer and we stop. LangGraph owns
this loop and the working state (the growing list of messages) -- we do not
reimplement reason/act, because that is exactly the wheel the library exists to
not reinvent.

WHAT STAYS OURS
---------------
The graph does not know about SSE, tabs, reconnects or the transcript. It emits
model/tool events; ``adapter.py`` turns those into our ``AgentEvent`` stream and
``runtime.py`` does everything with the browser. The graph is the brain; the
runtime is still the nervous system.

Tool results live in this graph's state and nowhere else. They are never
persisted and never replayed into a later run -- same ephemerality rule the
streaming contract enforces, here enforced by simply not writing them down.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.core.config import config

from .tools import TOOLS


@lru_cache(maxsize=1)
def get_graph() -> CompiledStateGraph:
    """
    Build and cache the compiled agent graph.

    Compilation is pure wiring and the bound model is reusable across runs, so
    there is no reason to pay for it per request. The cache also means the Gemini
    client is constructed once, after config (and the API key) is loaded.
    """
    # Full Gemini "Flash" models "think" by default, spending the output-token
    # budget on hidden reasoning before they answer. For a tool-driven lookup
    # agent that is pure overhead: it starved the visible reply, hit MAX_TOKENS
    # and returned nothing. ``thinking_budget=0`` turns it off so every token is
    # answer. "Flash-Lite" models don't think at all and reject the parameter
    # (400 INVALID_ARGUMENT); they also use fixed sampling and warn that
    # ``temperature`` is ignored. Both are therefore sent only to the full
    # models that honour them -- lite is already deterministic for our use.
    model_kwargs = dict(
        model=config.assistant_model,
        google_api_key=config.assistant_api_key,
        max_output_tokens=config.assistant_max_tokens,
    )
    if "lite" not in config.assistant_model.lower():
        # Deterministic: this answers questions about money from records, so
        # creativity is a liability, not a feature.
        model_kwargs["temperature"] = 0
        model_kwargs["thinking_budget"] = 0

    model = ChatGoogleGenerativeAI(**model_kwargs).bind_tools(TOOLS)

    async def call_model(state: MessagesState) -> dict:
        response = await model.ainvoke(state["messages"])
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("model", call_model)
    builder.add_node("tools", ToolNode(TOOLS))

    builder.add_edge(START, "model")
    # tools_condition routes to "tools" when the model asked for tool calls,
    # and to END otherwise -- the single branch that makes this a loop and not
    # a line.
    builder.add_conditional_edges("model", tools_condition)
    builder.add_edge("tools", "model")

    return builder.compile()
