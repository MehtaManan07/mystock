"""
Assistant Widgets

A widget is authoritative, backend-owned display. It exists for two reasons,
and both come down to not trusting a weak language model with things it must not
get wrong:

  1. ACTION -- the user has to *act* on something markdown cannot express
     (confirming a write before it happens: ``ConfirmActionWidget``).
  2. FINANCIAL DISPLAY -- a list of money rows (bills, and later payments /
     ledger) whose numbers, totals and links must be exact. The backend renders
     these as a structured payload the frontend draws verbatim, so the model
     never reformats them, drops a row, or mangles a link.

The second case is a deliberate reversal of the old "lists are always markdown"
rule. The reason is privacy *and* correctness: a widget's rows travel to the
browser out-of-band (as a tool ``artifact``), so they are never placed in the
model's context at all. A 14-row customer ledger that used to be dumped into the
prompt now never reaches the model -- only a one-line summary does. The weak
model cannot leak, miscount, or restyle data it never sees.
"""

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ConfirmActionField(BaseModel):
    """A single label/value line shown in the confirmation summary."""

    label: str = Field(..., max_length=60, description="Field name, e.g. 'Amount'")
    value: str = Field(..., max_length=200, description="Pre-formatted display value, e.g. 'Rs 10,000.00'")


class ConfirmActionWidget(BaseModel):
    """
    Asks the user to approve a pending write before it is applied.

    The agent never writes directly. It stages the intended change, emits this
    widget, and waits for the user's decision against `action_id`.
    """

    type: Literal["confirm_action"] = "confirm_action"
    action_id: str = Field(
        ..., description="Opaque id of the staged action; the client echoes it back with the decision"
    )
    title: str = Field(..., max_length=120, description="What is about to happen, e.g. 'Record expense'")
    fields: List[ConfirmActionField] = Field(
        default_factory=list, description="Summary of the staged change, in display order"
    )
    confirm_label: str = Field("Confirm", max_length=30)
    cancel_label: str = Field("Cancel", max_length=30)
    destructive: bool = Field(
        False, description="Render the confirm control as destructive (deletes, reversals)"
    )


class TableColumn(BaseModel):
    """A column header plus how its cells should be aligned."""

    label: str = Field(..., max_length=60, description="Column header, e.g. 'Amount'")
    align: Literal["left", "right"] = Field(
        "left", description="'right' for money and other numbers, 'left' otherwise"
    )


class TableCell(BaseModel):
    """
    One cell. A plain value, or a link when ``href`` is set.

    Keeping the link on the cell -- rather than inventing a bill-specific widget
    -- is what makes this table generic: any tool can mark any cell as a link
    (open a bill, a payment, a contact) without a new widget type.
    """

    text: str = Field(..., max_length=200, description="Pre-formatted display value")
    href: Optional[str] = Field(
        default=None,
        max_length=300,
        description="In-app link opened in a new tab; null for a plain cell",
    )


class TableWidget(BaseModel):
    """
    Authoritative tabular display, drawn verbatim by the frontend.

    The model never receives these rows -- they travel as a tool artifact and
    React draws them. The model gets only ``summary`` worth of information (a
    count and a total) to write a one-line lead. This one widget serves every
    list the assistant shows: bills now, ledger / transactions / summaries next.

    ``rows`` are positional: each inner list lines up with ``columns`` by index.
    """

    type: Literal["table"] = "table"
    title: Optional[str] = Field(
        default=None, max_length=200, description="e.g. 'Bills for Dabster (last 14 days)'"
    )
    summary: Optional[str] = Field(
        default=None, max_length=200, description="e.g. '14 bills · Rs 2,64,575 total'"
    )
    columns: List[TableColumn] = Field(default_factory=list)
    rows: List[List[TableCell]] = Field(
        default_factory=list, description="Each row's cells, aligned to columns by index"
    )
    truncation_note: Optional[str] = Field(
        default=None, max_length=200, description="Set when more rows exist than are shown"
    )


# A discriminated union: the `type` field already on the wire picks the member,
# so adding a widget is additive -- an old client meets an unknown `type`, not a
# changed shape.
Widget = Annotated[
    Union[ConfirmActionWidget, TableWidget],
    Field(discriminator="type"),
]
