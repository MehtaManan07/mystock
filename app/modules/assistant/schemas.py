"""
Assistant DTOs (Data Transfer Objects)

The client-to-server half of the contract. The server-to-client half is the
event stream in `events.py`.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SendMessageDto(BaseModel):
    """Start a run by sending a user message."""

    thread_id: Optional[str] = Field(
        None, description="Existing thread to continue; omit to start a new one"
    )
    content: str = Field(..., min_length=1, max_length=2000, description="The user's message")


class ActionDecisionDto(BaseModel):
    """The user's answer to a `confirm_action` widget."""

    decision: Literal["confirm", "cancel"] = Field(..., description="Whether to apply the staged write")
