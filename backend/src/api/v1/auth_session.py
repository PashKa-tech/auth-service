import uuid
from fastapi import APIRouter, Depends, Request, HTTPException, status
from src.api.deps import (
    get_auth_service,
    get_current_user,
    requires_fresh_auth
)
from src.services.auth import AuthService
from src.models.user import User
from src.schemas.common import UnifiedResponse

router = APIRouter()

@router.get("/sessions", response_model=UnifiedResponse)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    sessions = await auth_service.session_repo.list_active_by_user(current_user.id)
    data = [
        {
            "id": str(s.id),
            "ip_address": s.ip_address,
            "location": s.location,
            "user_agent": s.user_agent,
            "os_info": s.os_info,
            "browser_info": s.browser_info,
            "device_type": s.device_type,
            "created_at": s.created_at.isoformat() + "Z",
            "expires_at": s.expires_at.isoformat() + "Z"
        }
        for s in sessions
    ]
    return UnifiedResponse(success=True, data=data)

@router.delete("/sessions/{session_id}", response_model=UnifiedResponse)
async def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(requires_fresh_auth), # Step-up auth required!
    auth_service: AuthService = Depends(get_auth_service)
):
    current_session_id = getattr(request.state, "session_id", None)
    if str(current_session_id) == str(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Cannot revoke current active session. Use logout instead."
        )

    success = await auth_service.revoke_specific_session(current_user.id, session_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or already revoked")
        
    return UnifiedResponse(success=True, message="Session revoked successfully.")

@router.get("/me/audit", response_model=UnifiedResponse)
async def get_audit_history(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    logs = await auth_service.get_user_audit_logs(current_user.id, limit=30)
    
    formatted_logs = []
    for log in logs:
        formatted_logs.append({
            "id": str(log.id),
            "action": log.action,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "timestamp": log.timestamp.isoformat() + "Z",
            "metadata": log.metadata_json
        })
        
    return UnifiedResponse(success=True, data=formatted_logs)
