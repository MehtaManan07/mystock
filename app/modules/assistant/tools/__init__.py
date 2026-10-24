"""
The tools the agent is allowed to call.

A tool is the *only* way the model touches the business. It never sees the
database and never gets raw rows; it asks for a named, typed capability and
gets back a short piece of text it can reason over. That boundary is the whole
safety story for the read layer -- the model cannot query anything we did not
deliberately expose here.

Every tool in this package is READ-ONLY. Writes (issuing a bill, recording a
payment) are a different animal: they go through the human-in-the-loop path and
do not belong here. Keeping reads and writes in separate layers means "can the
agent do this without asking" is answered by *which list the tool is in*, not by
remembering a flag.

DB ACCESS
---------
Tools are async and the database is synchronous, so every tool that reads data
goes through a service whose methods already wrap their work in ``run_db`` --
one hop onto a threadpool, the session opened and closed there, nothing blocking
the event loop. Tools therefore ``await`` a service; they never open a session.

LAYOUT
------
One module per business domain (``products.py``, ``contacts.py``, ...), each
owning its tool(s) plus a ``LABELS`` dict of user-facing chip text. This file is
the only place that knows the full set: to add a tool, write it in its domain
module (or a new one) and register it in ``_MODULES`` below -- nothing else
changes. ``graph.py`` imports ``TOOLS``; ``adapter.py`` imports ``label_for``.
"""

from __future__ import annotations

from . import contacts, expenses, products, summary, transactions

# Every domain module that contributes tools. Add a module here (and it must
# expose a tool callable + a LABELS dict) and its tools light up everywhere.
_MODULES = [summary, products, contacts, transactions, expenses]

# The tools the agent may call. Order is the order the model sees them in.
TOOLS = [
    summary.get_business_summary,
    products.find_products,
    contacts.find_contacts,
    transactions.get_transactions,
    expenses.get_expense_summary,
]

# The one-line present-tense label the UI shows while each tool runs. The label
# is user-facing and must read like an action ("Pulling up ...") -- never the
# bare function name, which means nothing to the owner and leaks our internals
# into the chat. Assembled from each domain module's LABELS.
TOOL_LABELS: dict[str, str] = {}
for _module in _MODULES:
    TOOL_LABELS.update(_module.LABELS)


def label_for(tool_name: str) -> str:
    """The user-facing chip label for a tool, with a safe generic fallback."""
    return TOOL_LABELS.get(tool_name, "Working on it")


__all__ = ["TOOLS", "TOOL_LABELS", "label_for"]
