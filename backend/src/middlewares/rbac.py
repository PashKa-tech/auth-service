from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from src.core.security import verify_access_token
from src.core.context import get_request_id

class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Statelessly check prefix to enforce admin roles
        if path.startswith("/api/v1/auth/admin"):
            token = request.cookies.get("access_token")
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            
            if not token:
                request_id = request.headers.get("X-Request-ID") or get_request_id() or "-"
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "UNAUTHORIZED",
                            "message": "Authentication credentials were not provided.",
                            "details": {}
                        },
                        "meta": {"version": "v1", "request_id": request_id}
                    }
                )
            
            payload = await verify_access_token(token)
            if not payload:
                request_id = request.headers.get("X-Request-ID") or get_request_id() or "-"
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "UNAUTHORIZED",
                            "message": "Invalid or expired access token.",
                            "details": {}
                        },
                        "meta": {"version": "v1", "request_id": request_id}
                    }
                )
                
            role = payload.get("role")
            if role != "admin":
                request_id = request.headers.get("X-Request-ID") or get_request_id() or "-"
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "FORBIDDEN",
                            "message": "Forbidden: insufficient permissions",
                            "details": {}
                        },
                        "meta": {"version": "v1", "request_id": request_id}
                    }
                )
                
        return await call_next(request)
