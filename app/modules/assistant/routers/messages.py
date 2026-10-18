"""Taking a turn: say something and start an answer."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.users.auth import TokenData, get_current_user

from ..runtime import start_turn
from ..schemas import MessageResponse, SendMessageDto, SendMessageResponse

router = APIRouter(prefix="/messages", tags=["assistant"])


@router.post("", response_model=SendMessageResponse)
async def send_message(
    dto: SendMessageDto,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Say something and start an answer.

    Returns as soon as the run exists, before any token has been generated.
    The client then opens the stream with the returned `run_id`. Responding
    only once the answer was complete would defeat the entire design.

    A null `thread_id` starts a new conversation; `start_turn` creates the
    thread and the resolved id comes back on the run.
    """
    live, message = await start_turn(current_user.user_id, dto.thread_id, dto.content)

    return SendMessageResponse(
        thread_id=live.thread_id,
        run_id=live.id,
        message=MessageResponse.model_validate(message),
    )
