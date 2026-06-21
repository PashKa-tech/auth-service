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
    except Exception:
        return False

async def hash_password(password: str) -> str:
    """Hash a password using Argon2id without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, hash_password_sync, password)

async def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its Argon2id hash without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, verify_password_sync, password, hashed_password)

def create_access_token_sync(
    subject: str | uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    session_id: uuid.UUID,
    expires_delta: timedelta | None = None,
    custom_claims: dict | None = None
) -> str:
    """Generate a short-lived JWT Access Token synchronously."""
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
    
    if custom_claims:
        payload.update(custom_claims)
    
    from src.core.keys import get_rsa_keys
    private_key, _, _ = get_rsa_keys()
    
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "auth-service-key-1"})

async def create_access_token(
    subject: str | uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    session_id: uuid.UUID,
    expires_delta: timedelta | None = None,
    custom_claims: dict | None = None
) -> str:
    """Generate a short-lived JWT Access Token without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, 
        create_access_token_sync, 
        subject, tenant_id, role, session_id, expires_delta, custom_claims
    )

def verify_access_token_sync(token: str) -> dict | None:
    """Verify and decode a JWT Access Token synchronously."""
    try:
        from src.core.keys import get_rsa_keys
        _, public_key, _ = get_rsa_keys()
        
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=settings.APP_NAME
        )
        if payload.get("type"):
            return None
        return payload
    except (jwt.PyJWTError, ValueError):
        return None

async def verify_access_token(token: str) -> dict | None:
    """Verify and decode a JWT Access Token without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, verify_access_token_sync, token)

def generate_opaque_token() -> str:
    """Generate a cryptographically secure 256-bit entropy token."""
    # secrets.token_urlsafe(32) generates about 43 chars containing 256 bits of entropy
    return secrets.token_urlsafe(32)

def hash_opaque_token(token: str) -> str:
    """Hash an opaque token using SHA-256 for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_mfa_token_sync(user_id: uuid.UUID, tenant_id: uuid.UUID, extra_payload: dict | None = None) -> str:
    """Generate a short-lived (5 min) MFA challenge token synchronously."""
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

async def create_mfa_token(user_id: uuid.UUID, tenant_id: uuid.UUID, extra_payload: dict | None = None) -> str:
    """Generate a short-lived MFA challenge token without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, create_mfa_token_sync, user_id, tenant_id, extra_payload)

def verify_mfa_token_sync(token: str) -> dict | None:
    """Verify and decode a short-lived MFA challenge token synchronously."""
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

async def verify_mfa_token(token: str) -> dict | None:
    """Verify and decode a short-lived MFA challenge token without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, verify_mfa_token_sync, token)

def verify_pkce(verifier: str, challenge: str, method: str = "S256") -> bool:
    """Verify code_verifier against code_challenge using challenge method."""
    import secrets
    if method == "plain":
        return secrets.compare_digest(verifier, challenge)
    elif method == "S256":
        import hashlib
        import base64
        # Calculate SHA-256 hash
        hashed = hashlib.sha256(verifier.encode("utf-8")).digest()
        # Base64url encode and remove padding
        calculated = base64.urlsafe_b64encode(hashed).decode("utf-8").replace("=", "")
        return secrets.compare_digest(calculated, challenge)
    return False

async def check_pwned_password(password: str) -> bool:
    """Check if password has been compromised using HaveIBeenPwned k-anonymity API."""
    import hashlib
    import httpx
    
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    
    try:
        from src.core import http_client as http_client_module
        client_to_use = http_client_module.http_client
        
        if client_to_use:
            resp = await client_to_use.get(f"https://api.pwnedpasswords.com/range/{prefix}")
        else:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
                
        if resp.status_code == 200:
            # The response contains suffix:count lines
            hashes = (line.split(':') for line in resp.text.splitlines())
            for h, count in hashes:
                if h == suffix:
                    return True # Found in breach
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to check HaveIBeenPwned: {e}")
        
    return False
