from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from urllib.parse import urlparse
import uuid

from src.database import get_db
from src.config import settings
from src.models.saml import SamlConnection
from src.models.user import User

router = APIRouter()

def get_saml_auth(request: Request, connection: SamlConnection):
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    
    url_data = urlparse(str(request.url))
    req_data = {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': request.headers.get("Host", url_data.netloc),
        'server_port': url_data.port,
        'script_name': request.url.path,
        'get_data': request.query_params._dict,
        'post_data': {}
    }
    
    saml_settings = {
        "strict": True,
        "debug": settings.DEBUG,
        "sp": {
            "entityId": f"{settings.API_BASE_URL}/api/v1/auth/saml/metadata",
            "assertionConsumerService": {
                "url": f"{settings.API_BASE_URL}/api/v1/auth/saml/acs",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": ""
        },
        "idp": {
            "entityId": connection.idp_entity_id,
            "singleSignOnService": {
                "url": connection.idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "x509cert": connection.idp_x509_cert
        }
    }
    
    auth = OneLogin_Saml2_Auth(req_data, custom_base_path=None, old_settings=saml_settings)
    return auth

@router.get("/saml/login")
async def saml_login(
    request: Request,
    domain: str,
    db: AsyncSession = Depends(get_db)
):
    """Initiate SAML Login flow based on email domain."""
    result = await db.execute(select(SamlConnection).where(SamlConnection.domain_mapping == domain, SamlConnection.is_active == True))
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=400, detail="SAML not configured for this domain")
        
    auth = get_saml_auth(request, connection)
    sso_built_url = auth.login()
    
    return {"redirect_url": sso_built_url}

@router.post("/saml/acs")
async def saml_acs(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Assertion Consumer Service for SAML responses."""
    form_data = await request.form()
    
    # We need the connection context. Normally we'd extract the issuer from the raw SAML response first.
    # For demonstration, assume a single connection or find by state/RelayState.
    raise HTTPException(status_code=501, detail="SAML ACS parsing implemented for demo purposes.")

