# Assistant tools — v0 / v1 / v2 roadmap

What the KC agent can *do*, phased. Review and approve before we build.

## Principles

- **Memory is the database, not the chat.** The agent learns the business by
  *calling tools*, not by remembering long conversations. So the tool set is the
  real product — this list is what the assistant actually knows how to do.
- **Reads are autonomous; writes are approved.** Anything that only *looks* runs
  on its own. Anything that *changes data* (a bill, a payment, a new customer) is
  **staged and shown for confirmation** before it happens (HITL). Mom & dad
  always see "I'm about to do X — ok?" for writes.
- **Tool results stay compact.** We return a short answer + the number that
  matters, not 50-row dumps (token budget + readability on mobile).
- Every tool is a thin wrapper over a service that **already exists** — no new
  business logic, just an agent-facing door to it.

Legend: 🟢 read (autonomous) · 🔴 write (needs approval / HITL)

## Why curated tools, not LLM-written SQL (decided 2026-10-22)

We considered one generic `run_query(sql)` tool (LLM writes SQL from the schema)
vs. hand-built tools. **Decision: curated, parameterized tools.** Reasons:

- **It's a money app** — text-to-SQL's failure mode is a *confidently wrong
  number* (wrong balance-sign, missed soft-delete). Worst possible bug here.
- **Business logic lives in services** — e.g. "expenses" = `Payment.type ==
  'expense'`, balance conventions, GST, Indian formatting. Raw SQL bypasses and
  re-derives them wrong; curated tools reuse the same code the UI already trusts.
- **Safety** — no LLM-generated SQL on the prod DB; only the exact reads we allow.
- **Verifiable** — each tool is testable against known DB values.

To keep flexibility without the risk, tools are **parameterized** (one
`get_sales(period, contact?)` covers many phrasings) — the LLM *chooses and fills
in* trusted queries, it doesn't *author* them.

**Escape hatch (maybe v2+, power-user only):** if a long tail of unanticipated
questions shows up, add ONE guarded `run_read_query` — read-only DB role, over
curated views (not raw tables), SELECT-only + forced LIMIT + statement timeout.
Not for mom & dad; only if real usage demands it.

---

## v0 — "Answer questions about my business" (read-only)

Goal: your parents can *ask* anything about the shop and get a grounded answer.
No risk — nothing changes. This is the trust-building release.

| Tool | 🟢/🔴 | What it answers | Backed by |
|---|---|---|---|
| `get_business_summary` ✅ | 🟢 | Sales, cash movement and units by period (default: this month); current stock, account balances and open bills | `DashboardService` |
| `get_stock` | 🟢 | "How much of X do we have?" / "What's running low?" | `ProductsService` + `ContainerProductsService` |
| `find_product` | 🟢 | "What's the price/SKU of X?" product lookup | `ProductsService.find_all(search)` |
| `get_contact_balance` | 🟢 | "How much does Dindayal owe us?" | `ContactsService.find_one/find_all` |
| `find_contact` | 🟢 | "Do we have a customer named X? their phone?" | `ContactsService.find_all(search)` |
| `get_sales` | 🟢 | "What did we sell this week / to X?" | `TransactionsService.list_transactions` |
| `get_expense_summary` | 🟢 | "What did we spend on, this month?" | `PaymentsService.get_summary` |

**v0 done = the assistant is a useful read-only business dashboard you talk to.**

---

## v1 — "Do the small stuff for me" (first approved writes)

Goal: the agent starts *acting*, but every change is confirmed first. These are
the low-risk, high-frequency writes — the daily bookkeeping chores.

| Tool | 🟢/🔴 | What it does | Backed by |
|---|---|---|---|
| `record_expense` | 🔴 | "Note ₹2,000 for diesel" → stage expense, confirm, save | `PaymentsService.create` |
| `record_payment` | 🔴 | "Dindayal paid ₹5,000" → apply against their balance | `TransactionsService.record_payment` |
| `create_contact` | 🔴 | "Add a new customer, Mahesh Traders, phone…" | `ContactsService.create` |
| `update_contact` | 🔴 | "Fix Mahesh's phone number" | `ContactsService.update` |
| `get_contact_ledger` | 🟢 | "Show Dindayal's recent transactions & payments" | `TransactionsService.list` + `PaymentsService` |
| `find_bills` | 🟢 | "Give me all Dabster bills" — every invoice for a customer, across both stores | `TransactionsService` + `PdfInvoiceService` *(union — see below)* |

**v1 done = the agent handles everyday bookkeeping with a confirm tap.**
This is where the durable HITL machinery (Phase 4) earns its keep.

### `find_bills` — the unified bills tool (spec)

> **Why this is one tool, not two.** To a shop owner, "a bill" is one concept —
> but in the data it lives in **two tables**: a sale generates a bill
> (`transactions`, PDF at `invoice_url`), and a bill can also be an archived /
> uploaded PDF (`pdf_invoices`, PDF via download endpoint). "All Dabster bills"
> is the **union** of both. If we exposed two tools and hoped the model merged
> them, it would often return a *confidently partial* list — the worst failure
> mode for a money app. So we hide the split behind **one** curated tool.

**The union is clean — the data already supports it:**

- Both tables draw bill numbers from **one shared sequence** (`next_sale_number`
  unions `transactions` + `pdf_invoices` + reservations), format `SALE-NNNN`.
- So every number is **unique across both tables** → **no dedup problem**, and
  `SALE-NNNN` is the natural merge/sort key.

**Behaviour:**

```
find_bills(customer, days=None, source=None)
  → union of:
      • sale transactions for that contact  (label: "sale")
      • pdf_invoices for that contact        (label: "archived PDF")
  → sorted by SALE-NNNN (newest first), each row labelled with its source,
    capped at MAX_ROWS with the usual "... and N more" note.
```

- `customer` — name/phone; disambiguates like `get_transactions` (if it matches
  >1 contact, return the choices instead of a bill list).
- `days` — optional window; `None` = all time.
- `source` — optional filter (`sale` / `pdf`) for "only the uploaded ones" etc.
- Each row: `SALE-NNNN | date | customer | total | source`.

**Forward-compatible with the planned invoice-track merge.** The owner intends to
eventually fold `pdf_invoices` into `transactions` (one write track). This tool is
**insulated from that**: when the tables merge, we swap `find_bills`' *internals*
(query one table instead of two) — its **signature, output, and the model's
behaviour don't change**. So the agent ships now and never depends on the backend
merge landing.

**This is also where "give me the actual PDF files" will hang.** Both sources
carry a retrievable PDF (`transaction.invoice_url`, `pdf_invoice` download). Once
the chat UI can render **download chips** (an authenticated fetch → blob, reusing
the Bills-page download code), `find_bills` is the tool that returns those refs.
Until then it lists bills as text and points to the Bills page to download.
*(Tracked separately — needs frontend work, not a tool change.)*

> **Supersedes** the `find_bill` row previously parked in v2 (which only saw
> `pdf_invoices` and would have missed sale-generated bills).

---

## v2 — "Run the hard workflows" (billing, GST, warehouse, analytics)

Goal: the agent does the complex, multi-step, higher-stakes jobs. All writes
still confirmed; some produce documents.

| Tool | 🟢/🔴 | What it does | Backed by |
|---|---|---|---|
| `create_sale` / `make_bill` | 🔴 | "Make a bill: 10 boxes to Dindayal at ₹X" → stage full sale (line items + stock deduction), confirm, create | `TransactionsService.create_sale` |
| `generate_pdf_bill` | 🔴 | Produce the PDF invoice for a sale (the KC billing flow) | `PdfInvoiceService` + invoice gen |
| ~~`find_bill`~~ → moved to v1 | 🟢 | *Replaced by the unified `find_bills` (v1), which spans both bill stores — see v1 spec* | — |
| `create_purchase` | 🔴 | "We restocked 50 reams from vendor Y" | `TransactionsService.create_purchase` |
| `where_is_product` | 🟢 | "Which container is SKU X in?" warehouse location | `ContainerProductsService.get_containers_for_product` |
| `get_inventory_history` | 🟢 | "Show stock movement for X" | `InventoryLogsService.get_logs_for_product` |
| `get_gst_report` | 🟢 | "GST summary for last month" | `GstReportsService.report` |
| `get_sales_analytics` | 🟢 | "Top customers / best-selling products this quarter" | `TransactionsService` aggregates |

**v2 done = the agent can run the full shop — billing, tax, warehouse, insight.**

---

## Open questions for your review

1. **Where does billing go — v1 or v2?** It's the single most-wanted thing
   (make a bill), but also the most complex (line items, stock, PDF) and riskiest
   write. I've put it in **v2** so the HITL plumbing is battle-tested on small
   writes first. Move it up if it's the priority.
2. **Any tool here that should NOT exist** (e.g. you never want the agent
   touching purchases, or editing contacts)? Cutting is cheap now.
3. **Anything missing** your parents would actually ask for that isn't listed?
4. **v0 scope** — is 7 read tools the right first release, or trim to the 3–4
   you'd use daily (summary, stock, balance, sales)?
