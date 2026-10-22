# Agent graph — LangGraph integration

Turn the assistant from a straight line (`history → stream text`) into a real
reason→act→observe **graph**, with **selective HITL** (autonomous reads,
approval-gated writes).

## Ownership split (the whole design in one table)

| Layer | Owner |
|---|---|
| Model ↔ tool loop, working state, durable `interrupt()`/resume | **LangGraph** |
| Tools (thin wrappers over our services) | LangChain `@tool` |
| Browser transport: SSE, multi-tab fan-out, reconnect/backlog | **ours** (`runtime.py`) |
| Chat transcript persistence (`Message`) | **ours** |
| LangGraph stream → our `AgentEvent`s | **new adapter** (small) |

Rules that must survive every phase:
- Ephemeral events (`run_status`, `tool_call_*`) are NEVER persisted and NEVER
  fed back to the model (`events.py` EVENT_CLASSES already enforces this).
- The agent never writes directly — writes are staged, approved, then applied.
- Transcript reads identically whether watched live or opened later.

---

## Phase 0 — Foundations (deps + provider + config)

- [x] 0.1 Add `langgraph`, `langchain-core`, provider client (`langchain-groq`
      or `langchain-openai`) to `requirements.txt`; pin versions
- [x] 0.2 Pick provider + model; add `ASSISTANT_MODEL`, `ASSISTANT_API_KEY`,
      `ASSISTANT_MAX_TOKENS` to settings/env (no key in code)
- [x] 0.3 Confirm async DB session is available to tool handlers (tools query
      Postgres over the GCP tunnel — latency is real; `throttled` matters)
      → app is sync SQLAlchemy + `run_db(fn)`/`asyncio.to_thread`; tools do
      `await run_db(lambda db: Service.read(db, ...))`. No async engine needed.
- [x] 0.4 Smoke test: a bare `ChatGroq` call streams tokens — **PASSED** on
      `openai/gpt-oss-20b` (throwaway smoke script, since removed).
      Account has `openai/gpt-oss-120b` / `openai/gpt-oss-20b` / `qwen/qwen3.8-27b`
      as chat models (default 20b for budget; 120b available for quality).

## Phase 1 — Graph skeleton + adapter (ONE read tool, end to end)

Goal: a real model calls one real tool and streams a grounded answer through
our existing SSE pipe, with a live tool chip. No writes, no HITL yet.

- [x] 1.1 Define the LangGraph graph: `model` node + `tools` node + conditional
      edge (tool_calls? → tools → model; else → END)
- [x] 1.2 First tool: `get_business_summary()` (dashboard read path) — `@tool`,
      wraps `DashboardService.get_dashboard_data` via `run_db`; returns a
      compact, Indian-formatted text snapshot. (No `expenses` module exists;
      the dashboard already aggregates income/expenses/stock/outstanding.)
- [x] 1.3 Build the **adapter**: consume `graph.astream_events(...)` and map →
      our `AgentEvent`s:
      - model text deltas → `text_message_start/content/end`
      - tool start → `tool_call_start` (user-facing `label`, not tool name)
      - tool end → `tool_call_end`
      - status gaps → `run_status` (`thinking`/`generating`)
- [x] 1.4 Rewrite `run_agent` in `agent.py` to drive the graph via the adapter
      instead of streaming `StubLLM`; keep the same `AsyncIterator[AgentEvent]`
      signature so `runtime.py` is untouched
- [x] 1.5 Working state: build the graph's input messages from persisted
      history ONLY (reuse `build_context`'s budget trim); tool results live in
      graph state, never in the transcript
- [x] 1.6 Retire `StubLLM` path: `get_llm()` no longer used by the graph; keep
      the file only if a stub is still wanted for tests, else delete
- [ ] 1.7 Verify: ask a question that needs the tool → chip appears → grounded
      answer streams → reload shows transcript without the chip (ephemeral held)

## Phase 2 — Tool layer (read tools over the business)

- [ ] 2.1 `get_stock(product?/low_only)` → inventory service
- [ ] 2.2 `get_sales(period, contact?)` → transaction service
- [ ] 2.3 `get_contact_balance(contact)` → contacts service
- [ ] 2.4 `get_expense_breakdown(period)` → categorized expenses
- [ ] 2.5 Tool-result shaping: return compact structured data, not giant tables
      (token budget — widgets doc already argues "answer + link", not 50 rows)
- [ ] 2.6 System prompt: enumerate tools + the Indian-number / "say so if no
      data" rules already in `SYSTEM_PROMPT`
- [ ] 2.7 Verify each tool against known values from the real DB

## Phase 3 — Guardrails (the control edges)

- [ ] 3.1 Max tool-call iterations per run (stop runaway loops) → on exceed,
      emit a graceful `run_error: internal` with a safe message
- [ ] 3.2 Tool-failure handling: a raising tool feeds an error observation back
      to the model (or fails the run cleanly) — never a raw traceback to client
- [ ] 3.3 Rate-limit path: provider 429 → `run_status: throttled` +
      `retry_in_seconds`; `run_error: rate_limited` if unrecoverable
- [ ] 3.4 Cancellation: confirm stopping consumption still halts the graph
      between steps (reuse existing cancel; add a test)
- [ ] 3.5 Context budget respected across loop steps (history + tool results)

## Phase 4 — Durable HITL write tool (the real feature)

Uses LangGraph `interrupt()` + a checkpointer, scoped to **suspended-run state
only**. Our DB still owns the transcript.

- [ ] 4.1 Add a LangGraph checkpointer (Postgres saver) — owns graph/interrupt
      state, NOT the transcript; keyed by run
- [ ] 4.2 First write tool (e.g. `record_expense`) STAGES the change and calls
      `interrupt()` with a `ConfirmActionWidget` payload (reuse `widgets.py`)
- [ ] 4.3 On interrupt: adapter emits the `widget` event; run parks in
      `RunStatus.INTERRUPTED` (state already exists in `models.py`)
- [ ] 4.4 Decision endpoint: `POST /api/assistant/runs/{run_id}/actions/{action_id}`
      taking `ActionDecisionDto` (already defined in `schemas.py`)
- [ ] 4.5 Idempotency guard so a confirmation can't be acted on twice
      (the `models.py:152` note); double-submit → 409/no-op
- [ ] 4.6 Resume: `confirm` → `Command(resume=...)` re-enters the graph, applies
      the write, continues; `cancel` → close the run, apply nothing
- [ ] 4.7 Durability test: emit widget → kill/reopen the SSE connection →
      approve → run resumes and completes (the whole point of durable HITL)
- [ ] 4.8 Frontend: wire `ConfirmActionWidget`'s confirm/cancel to the decision
      endpoint; reflect pending/approved/cancelled state

## Phase 5 — Verify + polish

- [ ] 5.1 Pyright clean on all new backend code
- [ ] 5.2 End-to-end: a read question, a write question (approved), a write
      question (cancelled), a cancelled mid-run, a rate-limit simulation
- [ ] 5.3 Update `docs/assistant-architecture.md` — replace the "one LLM swap
      point" section with the graph + HITL flow
- [ ] 5.4 Confirm no ephemeral leakage into transcript or model context after
      all the new event types

## Memory strategy (decided 2026-10-22)

KC conversations are **task-shaped, not companion-shaped** (ask a balance, make
a bill, check sales — a few turns, done). Therefore:
- **Threads stay short + task-scoped**; nudge "new chat" per task in the UI.
- **Real long-term memory = Postgres**, surfaced via *tools* on demand — NOT
  conversation history. A good lookup tool beats remembering 200 turns.
- **No summarization / RAG for now.** `build_context`'s char-trim
  (`MAX_CONTEXT_CHARS`) is sufficient because threads rarely outlive the window.
- Revisit summarization (threshold-triggered: compress oldest turns, keep recent
  verbatim) or `pgvector` RAG **only if** real usage shows long single threads.

## Open questions (resolve before/within the phase that needs them)

- Provider: Groq (free tier, fast) vs OpenAI (quality) — budget vs accuracy.
- Checkpointer store: same Postgres as the app, or separate schema? (keep the
  transcript/graph-state seam clean either way)
- How much tool-result detail to surface as widgets vs "answer + link to page".
- Streaming granularity: token-level deltas vs lifecycle-only for v1.
