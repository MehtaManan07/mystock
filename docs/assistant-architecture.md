# Assistant — Pre-LLM Agentic Architecture

The agent surface is built end-to-end **except the model itself**. Persistence,
streaming, cancellation, reconnect, and crash recovery are all real; `llm.py` is
the single stub. Swapping `StubLLM` for a real client (e.g. Groq) is a one-file
change behind `get_llm()`.

This document describes exactly what exists today.

---

## 1. Component map

How the pieces fit together, from the browser down to Postgres. The dashed
registry is **in-process, in-memory** state — it is the "live" half of a run and
is deliberately *not* a database row.

```mermaid
flowchart TB
    subgraph Browser["Browser — mystock-ui (React 19)"]
        AP["AssistantPage.tsx<br/>orchestrator: activeThreadId, runId,<br/>input, pendingMessage (instant echo)"]
        TL["ThreadList.tsx"]
        CV["Conversation.tsx<br/>history + pending echo + live msgs"]
        CP["Composer.tsx"]
        UA["hooks/useAssistant.ts<br/>react-query: threads CRUD,<br/>sendMessage, getRun, cancel"]
        URS["useRunStream.ts<br/>reducer: AgentEvent[] → RunState"]
        SR["streamRun.ts<br/>fetch+ReadableStream SSE reader<br/>(Bearer auth, Last-Event-ID resume)"]
        API["api/assistant.api.ts<br/>axios REST"]
    end

    subgraph Server["Server — mystock (FastAPI, single worker)"]
        subgraph Routers["routers/"]
            RT["threads.py<br/>list/create/get/rename/delete"]
            RM["messages.py<br/>POST /messages → start_turn"]
            RR["runs.py<br/>GET /runs/{id}, cancel,<br/>GET /runs/{id}/stream (SSE)"]
        end

        RUNTIME["runtime.py — start_turn()<br/>+ RunRegistry"]
        REG(["RunRegistry (in-memory)<br/>LiveRun: asyncio.Task + Queues<br/>seq, backlog, subscribers"])
        AGENT["agent.py — run_agent()<br/>builds context, yields events"]
        LLM["llm.py — StubLLM<br/>⚠️ ONLY STUB: keyword→reply,<br/>streams fragments"]

        subgraph Services["services/ (each call → run_db worker thread)"]
            TS["ThreadService"]
            MS["MessageService"]
            RS["RunService"]
        end

        EV["events.py<br/>AgentEvent union + EVENT_CLASSES<br/>(ephemeral / transcript / control)"]
        RI["response_interceptor<br/>(SSE route is @skip_interceptor)"]
    end

    PG[("Postgres (GCP VM, via SSH tunnel :5433)<br/>assistant_threads / _messages / _runs")]

    TL --> UA
    CP --> AP
    AP --> UA
    AP --> URS
    CV --> AP
    UA --> API
    URS --> SR
    API -->|"Authorization: Bearer"| Routers
    SR -->|"GET .../stream"| RR

    RM --> RUNTIME
    RT --> TS
    RR --> REG
    RR --> RS
    RUNTIME --> REG
    RUNTIME --> TS
    RUNTIME --> MS
    RUNTIME --> RS
    REG -.drives.-> AGENT
    AGENT --> LLM
    AGENT --> MS
    AGENT -. emits .-> EV
    REG -. persists reply .-> RS
    TS --> PG
    MS --> PG
    RS --> PG
    Routers -.wrapped by.-> RI

    classDef stub fill:#ffe2e2,stroke:#d33;
    classDef mem fill:#fff3cd,stroke:#e0a800,stroke-dasharray:4 3;
    class LLM stub;
    class REG mem;
```

---

## 2. The one-turn flow (send → answer)

This is the heart of the design. The POST returns **as soon as the run exists**,
*before* any token is generated; the browser then opens the SSE stream with the
returned `run_id`. Note the deliberate ordering in `start_turn`: **open the run
first** (that's what atomically claims the thread via the partial unique index),
*then* append the user message.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant AP as AssistantPage
    participant Q as react-query
    participant RM as POST /messages
    participant ST as start_turn (runtime)
    participant RS as RunService
    participant MS as MessageService
    participant REG as RunRegistry
    participant AG as run_agent
    participant LLM as StubLLM
    participant PG as Postgres
    participant SR as streamRun (SSE)
    participant URS as useRunStream

    U->>AP: type + send
    Note over AP: instant echo — set pendingMessage,<br/>clear input BEFORE await (0ms bubble)
    AP->>Q: useSendMessage.mutate(content, thread_id?)
    Q->>RM: POST /messages

    RM->>ST: start_turn(user, thread_id, content)
    alt new conversation (thread_id = null)
        ST->>RS: (thread first)
        ST-->>PG: ThreadService.create
    end
    ST->>RS: RunService.open  →  claims thread (unique idx)
    RS-->>PG: INSERT assistant_runs (status=running)
    ST->>MS: append_user_message
    MS-->>PG: INSERT assistant_messages (role=user)
    Note over ST,MS: if message insert fails → RunService.fail,<br/>don't leave the thread claimed forever
    ST->>REG: attach(record, run_agent)
    REG->>AG: spawn asyncio.Task (_drive)
    RM-->>Q: 200 {thread_id, run_id, message}
    Q-->>AP: onSuccess → optimistic ASSISTANT_THREADS update
    AP->>URS: set runId

    URS->>SR: openRunStream(runId)
    SR->>SR: fetch GET /runs/{id}/stream (Bearer)

    REG-->>SR: run_started
    AG-->>REG: run_status "thinking"  (ephemeral)
    AG->>MS: list_for_thread → build_context (≤12k chars)
    AG-->>REG: run_status "generating" (ephemeral)
    AG-->>REG: text_message_start
    loop each fragment
        LLM-->>AG: fragment
        AG-->>REG: text_message_content delta  (transcript)
        REG-->>SR: id:<seq> data:{...}
        SR-->>URS: onEvent → append delta
    end
    AG-->>REG: text_message_end

    Note over REG,PG: _conclude — PERSIST then ANNOUNCE
    REG->>RS: RunService.complete(reply.text, widget)
    RS-->>PG: INSERT assistant_message (role=assistant)<br/>+ run → completed
    REG-->>SR: run_finished (terminal, final)
    SR-->>URS: onComplete
    URS-->>AP: refetch thread → clear pendingMessage, reset, runId=null
```

**Why persist-before-announce:** a client that sees `run_finished` may reload
instantly. If the DB write were still in flight, the answer it just watched
appear would be missing. The window is milliseconds on a local DB — which is
exactly why it survives testing and breaks in production.

---

## 3. Event classes — what survives the run

Every event is exactly one of three classes (`EVENT_CLASSES`, enforced at import
time against the `AgentEvent` union). This is the rule that keeps the agent's own
thinking out of its future input.

```mermaid
flowchart LR
    subgraph EPH["EPHEMERAL — visible thinking"]
        E1["run_status (thinking/generating/throttled)"]
        E2["tool_call_start"]
        E3["tool_call_end"]
    end
    subgraph TR["TRANSCRIPT — the actual reply"]
        T1["text_message_start"]
        T2["text_message_content (delta)"]
        T3["text_message_end"]
        T4["widget"]
    end
    subgraph CT["CONTROL — stream bookkeeping"]
        C1["run_started"]
        C2["run_finished (terminal)"]
        C3["run_error (terminal)"]
    end

    EPH -->|"wiped on run end<br/>NEVER replayed to model<br/>NEVER persisted"| X1["UI only, live"]
    TR -->|"accumulated server-side → DB<br/>survives reload/restart"| PG[("assistant_messages")]
    CT -->|"meaningful only while connected"| X2["open/close stream"]
```

Two consequences that matter:
1. **The UI discards ephemerals when the run ends**, so a thread reads identically
   whether you watched it live or opened it an hour later (`useRunStream` drops
   `statusLabel`/`toolCalls` on terminal).
2. **Ephemerals are never fed back to the model.** `agent.py` builds context only
   from persisted `assistant_messages` (roles `user`/`assistant` only) — there is
   no path by which a status line can reach the prompt. On an ~8K TPM free tier,
   replaying "thinking…" would cost tokens to confuse the model.

---

## 4. Multi-tab watching + reconnect/resume

Any number of tabs can watch one run; each gets a backlog from its resume point
plus a live feed. Resume is by `Last-Event-ID` (the browser sets it on reconnect),
and the registry replays **durable events only** — so a client that drops and
returns sees the same transcript as one that never left.

```mermaid
sequenceDiagram
    autonumber
    participant T1 as Tab A
    participant T2 as Tab B
    participant RR as GET /runs/{id}/stream
    participant REG as RunRegistry
    participant Q as asyncio.Queue (per subscriber)

    T1->>RR: stream (after_seq=0)
    RR->>REG: subscribe(run, after_seq=0)
    Note over REG: under ONE lock: snapshot backlog<br/>AND register queue (no gap, no dupe)
    REG-->>RR: (backlog[], queue)
    RR-->>T1: replay backlog, then live frames
    REG-->>Q: new events pushed to all subscribers

    T2->>RR: stream (same run)
    RR->>REG: subscribe(run, after_seq=0)
    REG-->>T2: same backlog + live feed

    Note over T1,RR: connection drops
    T1->>RR: reconnect, Last-Event-ID: 7
    RR->>REG: subscribe(run, after_seq=7)
    REG-->>T1: only events with seq > 7 (durable only)

    Note over RR: every HEARTBEAT_SECONDS (15s) idle →<br/>": keepalive" comment frame<br/>(also detects a dead client: write raises)
    Note over REG: if run already finished at subscribe →<br/>queue gets sentinel None immediately
```

**Backlog is capped** (`MAX_BACKLOG_EVENTS = 2000`) so a long run can't grow
unbounded; the terminal event is always delivered regardless.

---

## 5. Lifecycle, cancellation & crash recovery

A run's *liveness* lives in memory (`LiveRun` = `asyncio.Task` + queues); its
*record* lives in Postgres. That split is why `status` can be stale after a crash.

```mermaid
stateDiagram-v2
    [*] --> running: RunService.open (INSERT, claims thread)
    running --> completed: agent finished → persist reply, then run_finished
    running --> cancelled: cooperative flag seen between events
    running --> failed: exception → generic error text, run_error
    running --> interrupted: process died (no in-memory survivor)
    interrupted --> [*]: reconcile_stale_runs() at startup (lifespan)
    completed --> [*]
    cancelled --> [*]
    failed --> [*]

    note right of cancelled
      Cancel sets live.cancelled = true.
      NOT Task.cancel(): a hard cancel could
      land mid-DB-write and vanish the answer.
      Loop checks the flag at a safe point.
    end note

    note right of interrupted
      One live run per thread is a DB guarantee
      (partial unique index where status='running').
      On boot, anything still 'running' had no
      survivor → closed as INTERRUPTED so it
      doesn't look live forever.
    end note
```

---

## 6. Key design invariants (read before changing anything)

| Invariant | Where enforced | Why |
|---|---|---|
| Persist reply **before** emitting terminal event | `runtime._conclude` | Client may reload on `run_finished`; the answer must already be in the DB. |
| Open run **before** appending user message | `runtime.start_turn` | The run row atomically claims the thread; message-first would store a question a rejected concurrent send can never answer. |
| One live run per thread | partial unique index `uq_assistant_runs_active_per_thread` | Makes "no concurrent runs" a DB guarantee, not a check-then-act race. Also what startup reconciliation scans. |
| Ephemerals never persisted / never replayed to model | `models.py` (2 roles only) + `agent.build_context` | Keeps the transcript stable across reloads; protects the token budget. |
| Cancellation is cooperative (flag, not `Task.cancel()`) | `runtime._drive` | A hard cancel could interrupt the DB write and vanish the answer. |
| SSE route skips the response interceptor | `@skip_interceptor` on `stream_run` | The interceptor buffers whole bodies; an endless stream would never reply. |
| `X-Accel-Buffering: no` on the stream | `runs.stream_run` | nginx buffers by default → whole answer arrives at once in prod only. |
| Message ordering by `id`, not `created_at` | `models.py` | PG `now()` is transaction-scoped; two rows in one txn share a timestamp. |
| Single worker only | `runtime.py` | Registry is process-local; scaling out needs Redis/Postgres pub-sub — this module is the only thing that changes. |

---

## 7. The only thing left to make it "real"

```mermaid
flowchart LR
    GI["get_llm()"] --> STUB["StubLLM<br/>keyword → canned reply,<br/>streams fragments at human pace"]
    GI -. one-file swap .-> REAL["GroqLLM (future)<br/>same stream() protocol"]
    classDef stub fill:#ffe2e2,stroke:#d33;
    class STUB stub;
```

Everything else — the token-stream interface, correlation `message_id`,
cancellation between fragments, context budget (`MAX_CONTEXT_CHARS = 12_000`),
Indian-number system prompt — already assumes a real streaming model. The stub
has the *shape* of the real problem so the swap is just a new `LLM` class and a
changed `get_llm()` return.
