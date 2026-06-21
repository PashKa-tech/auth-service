from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
from typing import List

from src.database import get_db
from src.api.deps import resolve_tenant, get_action_repository
from src.repositories.action import ActionRepository
from src.models.action import Action
from src.schemas.common import UnifiedResponse

router = APIRouter()

class ActionCreate(BaseModel):
    name: str
    trigger: str # "post-login"
    code: str

class ActionUpdate(BaseModel):
    name: str | None = None
    trigger: str | None = None
    code: str | None = None
    is_active: bool | None = None

class ActionResponse(BaseModel):
    id: str
    name: str
    trigger: str
    code: str
    is_active: bool

@router.get("", response_model=UnifiedResponse)
async def list_actions(
    repo: "ActionRepository" = Depends(get_action_repository)
):
    actions = await repo.get_all()
    
    data = [
        {
            "id": str(a.id),
            "name": a.name,
            "trigger": a.trigger,
            "code": a.code,
            "is_active": a.is_active
        }
        for a in actions
    ]
    return UnifiedResponse(success=True, data=data)

@router.post("", response_model=UnifiedResponse, status_code=status.HTTP_201_CREATED)
async def create_action(
    body: ActionCreate,
    repo: "ActionRepository" = Depends(get_action_repository)
):
    action = Action(
        tenant_id=repo.tenant_id,
        name=body.name,
        trigger=body.trigger,
        code=body.code,
        is_active=True
    )
    repo.add(action)
    await repo.db.commit()
    await repo.db.refresh(action)
    
    return UnifiedResponse(success=True, data={"id": str(action.id)})

@router.put("/{action_id}", response_model=UnifiedResponse)
async def update_action(
    action_id: uuid.UUID,
    body: ActionUpdate,
    repo: "ActionRepository" = Depends(get_action_repository)
):
    action = await repo.get_by_id(action_id)
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
        
    if body.name is not None: action.name = body.name
    if body.trigger is not None: action.trigger = body.trigger
    if body.code is not None: action.code = body.code
    if body.is_active is not None: action.is_active = body.is_active
    
    await repo.db.commit()
    return UnifiedResponse(success=True, data={"id": str(action.id)})

@router.delete("/{action_id}", response_model=UnifiedResponse)
async def delete_action(
    action_id: uuid.UUID,
    repo: "ActionRepository" = Depends(get_action_repository)
):
    action = await repo.get_by_id(action_id)
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
        
    await repo.delete(action)
    await repo.db.commit()
    return UnifiedResponse(success=True, message="Action deleted")
