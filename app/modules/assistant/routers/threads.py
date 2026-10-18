"""Conversations: list, create, fetch, rename and soft-delete a thread."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from app.modules.users.auth import TokenData, get_current_user

from ..schemas import CreateThreadDto, RenameThreadDto, ThreadDetail, ThreadSummary
from ..services import ThreadService

router = APIRouter(prefix="/threads", tags=["assistant"])


@router.get("", response_model=List[ThreadSummary])
async def list_threads(current_user: TokenData = Depends(get_current_user)):
    return await ThreadService.list_for_user(current_user.user_id)


@router.post("", response_model=ThreadSummary)
async def create_thread(
    dto: CreateThreadDto,
    current_user: TokenData = Depends(get_current_user),
):
    return await ThreadService.create(current_user.user_id, dto.title)


@router.get("/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: int,
    current_user: TokenData = Depends(get_current_user),
):
    """The whole conversation. Exactly what a reload shows."""
    return await ThreadService.get_with_messages(current_user.user_id, thread_id)


@router.patch("/{thread_id}", response_model=ThreadSummary)
async def rename_thread(
    thread_id: int,
    dto: RenameThreadDto,
    current_user: TokenData = Depends(get_current_user),
):
    return await ThreadService.rename(current_user.user_id, thread_id, dto.title)


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: int,
    current_user: TokenData = Depends(get_current_user),
):
    await ThreadService.soft_delete(current_user.user_id, thread_id)
    return {"message": "Conversation deleted"}
