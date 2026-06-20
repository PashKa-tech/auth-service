from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

@router.get("/.well-known/openid-configuration")
async def get_openid_configuration(request: Request):
    """OIDC Discovery Document."""
    base_url = str(request.base_url).rstrip("/")
    return {
        "issuer": base_url, # In a real scenario, this matches settings.APP_NAME or public URL
        "authorization_endpoint": f"{base_url}/authorize", # Our React app handles this
        "token_endpoint": f"{base_url}/api/v1/auth/oauth/token",
        "userinfo_endpoint": f"{base_url}/api/v1/auth/me",
        "jwks_uri": f"{base_url}/.well-known/jwks.json",
        "response_types_supported": ["code", "token", "id_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "claims_supported": ["sub", "iss", "aud", "exp", "iat", "email", "role", "tenant_id"]
    }

@router.get("/.well-known/jwks.json")
async def get_jwks():
    """JSON Web Key Set."""
    from src.core.keys import get_rsa_keys
    _, _, jwks = get_rsa_keys()
    return jwks
