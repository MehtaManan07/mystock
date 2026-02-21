"""
Drafts Router - API endpoints for managing transaction drafts
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.modules.users.auth import get_current_user, TokenData
from .service import DraftsService
from .schemas import CreateDraftDto, UpdateDraftDto, DraftResponse, CompleteDraftResponse
from .models import DraftType

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("", response_model=DraftResponse)
async def create_draft(
    dto: CreateDraftDto,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Create a new draft transaction.
    """
    draft = await DraftsService.create(current_user.user_id, dto)
    return draft


@router.get("", response_model=List[DraftResponse])
async def get_all_drafts(
    type: Optional[DraftType] = Query(None, description="Filter by draft type (sale or purchase)"),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get all drafts for the current user.
    Optionally filter by type.
    """
    drafts = await DraftsService.find_all_by_user(current_user.user_id, type)
    return drafts


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: int,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get a specific draft by ID.
    """
    draft = await DraftsService.find_one(current_user.user_id, draft_id)
    return draft


@router.patch("/{draft_id}", response_model=DraftResponse)
async def update_draft(
    draft_id: int,
    dto: UpdateDraftDto,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Update a draft.
    """
    draft = await DraftsService.update(current_user.user_id, draft_id, dto)
    return draft


@router.delete("/{draft_id}")
async def delete_draft(
    draft_id: int,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Delete a draft.
    """
    await DraftsService.delete(current_user.user_id, draft_id)
    return {"message": "Draft deleted successfully"}


@router.get("/{draft_id}/complete", response_model=CompleteDraftResponse)
async def get_complete_draft(
    draft_id: int,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get draft with hydrated products and containers.
    Optimized endpoint that returns full product and container details
    in a single request, eliminating N+1 queries.
    """
    return await DraftsService.get_complete_draft(current_user.user_id, draft_id)
