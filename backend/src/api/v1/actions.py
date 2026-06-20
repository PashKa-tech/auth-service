from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
from typing import List

from src.database import get_db
from src.api.deps import resolve_tenant
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
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    res = await db.execute(select(Action).where(Action.tenant_id == tenant_id))
    actions = res.scalars().all()
    
    data = [
        ActionResponse(
            id=str(a.id),
            name=a.name,
            trigger=a.trigger,
            code=a.code,
            is_active=a.is_active
        ).model_dump()
        for a in actions
    ]
    return UnifiedResponse(success=True, data=data)

@router.post("", response_model=UnifiedResponse, status_code=status.HTTP_201_CREATED)
async def create_action(
    body: ActionCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    action = Action(
        tenant_id=tenant_id,
        name=body.name,
        trigger=body.trigger,
        code=body.code,
        is_active=True
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    
    return UnifiedResponse(success=True, data={"id": str(action.id)})

@router.put("/{action_id}", response_model=UnifiedResponse)
async def update_action(
    action_id: uuid.UUID,
    body: ActionUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    res = await db.execute(select(Action).where(Action.id == action_id, Action.tenant_id == tenant_id))
    action = res.scalar_one_or_none()
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
        
    if body.name is not None: action.name = body.name
    if body.trigger is not None: action.trigger = body.trigger
    if body.code is not None: action.code = body.code
    if body.is_active is not None: action.is_active = body.is_active
    
    await db.commit()
    return UnifiedResponse(success=True, data={"id": str(action.id)})

@router.delete("/{action_id}", response_model=UnifiedResponse)
async def delete_action(
    action_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    res = await db.execute(select(Action).where(Action.id == action_id, Action.tenant_id == tenant_id))
    action = res.scalar_one_or_none()
    
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
        
    await db.delete(action)
    await db.commit()
    return UnifiedResponse(success=True, message="Action deleted")
