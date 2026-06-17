from fastapi import HTTPException, Depends, status
from src.models.user import User
from src.api.deps import get_current_user

ROLE_PERMISSIONS = {
    "admin": ["users:read", "users:write", "sessions:read", "sessions:write", "admin:access"],
    "manager": ["users:read", "sessions:read"],
    "user": ["profile:read", "profile:write"]
}

class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        user_permissions = ROLE_PERMISSIONS.get(current_user.role, [])
        if self.required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions"
            )
        return current_user
