"""
Assistant Widgets

Markdown handles all *display*. A widget exists only where the user has to
*act* on something, which markdown fundamentally cannot do. Today that is
exactly one case: confirming a write before it happens.

Deliberately not widgets: payment lists, summaries, stat cards, charts. Those
are display, and the existing pages already render them better than a chat
bubble can. Restating a 50-row table in the response costs ~1,750 tokens
against an 8K/min budget; an answer plus a link costs under 100.
"""

from typing import List, Literal

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


# Becomes Annotated[Union[...], Field(discriminator="type")] if a second widget
# is ever justified. Until then a single model keeps the client's switch honest.
Widget = ConfirmActionWidget
