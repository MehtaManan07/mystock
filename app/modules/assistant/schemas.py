"""Request and response payloads for the assistant endpoints.

Responses are built from ORM objects, so the models here are the boundary
between the database and the wire. Only what the client needs crosses it --
notably ``error_message`` is the safe, user-facing string, never raw
exception text, and the agent's thinking appears nowhere because it is never
stored in the first place.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# -- requests -------------------------------------------------------------


class CreateThreadDto(BaseModel):
    """Start a conversation. The title is usually left to the first message."""

    title: Optional[str] = Field(None, max_length=120)


class RenameThreadDto(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class SendMessageDto(BaseModel):
    """Post a user message. Omit `thread_id` to start a new thread."""

    thread_id: Optional[int] = Field(
        None, description="Existing thread to continue; omit to start one"
    )
    content: str = Field(
        ..., min_length=1, max_length=2000, description="The user's message"
    )


class ActionDecisionDto(BaseModel):
    """
    The user's answer to a `confirm_action` widget.

    The client sends only the decision; the action id is in the path. Nothing
    the model produced is re-sent at write time -- the server re-reads its own
    stored payload.
    """

    decision: Literal["confirm", "cancel"]


# -- responses ------------------------------------------------------------


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    widget: Optional[dict] = None
    created_at: datetime


class ThreadSummary(BaseModel):
    """A row in the conversation list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ThreadDetail(ThreadSummary):
    """A conversation and everything durable in it."""

    messages: List[MessageResponse] = []


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: int
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class SendMessageResponse(BaseModel):
    """
    What the client needs to start watching.

    `run_id` is returned before a single token exists; the client opens the
    stream with it. `thread_id` is echoed because the request may have
    created the thread.
    """

    thread_id: int
    run_id: int
    message: MessageResponse
