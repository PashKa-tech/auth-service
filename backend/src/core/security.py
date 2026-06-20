import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from src.config import settings

# Initialize Argon2id password hasher with configured parameters
ph = PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_COST,
    parallelism=settings.ARGON2_PARALLELISM,
)

import asyncio

def hash_password_sync(password: str) -> str:
    return ph.hash(password)

def verify_password_sync(password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, password)
    except VerifyMismatchError:
        return False

async def hash_password(password: str) -> str:
    """Hash a password using Argon2id without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, hash_password_sync, password)

async def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its Argon2id hash without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, verify_password_sync, password, hashed_password)

def create_access_token(
    subject: str | uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    session_id: uuid.UUID,
    expires_delta: timedelta | None = None
) -> str:
    """Generate a short-lived JWT Access Token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "role": role,
        "session_id": str(session_id),
        "iss": settings.APP_NAME,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def verify_access_token(token: str) -> dict | None:
    """Verify and decode a JWT Access Token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.APP_NAME
        )
        if payload.get("type"):
            return None
        return payload
    except (jwt.PyJWTError, ValueError):
        return None

def generate_opaque_token() -> str:
    """Generate a cryptographically secure 256-bit entropy token."""
    # secrets.token_urlsafe(32) generates about 43 chars containing 256 bits of entropy
    return secrets.token_urlsafe(32)

def hash_opaque_token(token: str) -> str:
    """Hash an opaque token using SHA-256 for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_mfa_token(user_id: uuid.UUID, tenant_id: uuid.UUID, extra_payload: dict | None = None) -> str:
    """Generate a short-lived (5 min) MFA challenge token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.MFA_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "type": "mfa_challenge",
        "iss": settings.APP_NAME,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_payload:
        payload.update(extra_payload)
        
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def verify_mfa_token(token: str) -> dict | None:
    """Verify and decode a short-lived MFA challenge token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.APP_NAME
        )
        if payload.get("type") != "mfa_challenge":
            return None
        return payload
    except (jwt.PyJWTError, ValueError):
        return None

def verify_pkce(verifier: str, challenge: str, method: str = "S256") -> bool:
    """Verify code_verifier against code_challenge using challenge method."""
    if method == "plain":
        return verifier == challenge
    elif method == "S256":
        import hashlib
        import base64
        # Calculate SHA-256 hash
        hashed = hashlib.sha256(verifier.encode("ascii")).digest()
        # Base64url encode and remove padding
        calculated = base64.urlsafe_b64encode(hashed).decode("utf-8").replace("=", "")
        return calculated == challenge
    return False
