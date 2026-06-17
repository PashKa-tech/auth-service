import uuid
import httpx
from urllib.parse import urlencode
from src.config import settings
from src.core.logging import logger
from src.repositories.oauth import OAuthRepository
from src.services.auth import AuthService
from src.models.user import User

class OAuthService:
    def __init__(self, oauth_repo: OAuthRepository):
        self.oauth_repo = oauth_repo
        self.tenant_id = oauth_repo.tenant_id

    def get_authorization_url(self, provider: str, state: str) -> str:
        """Generate redirect URL to OAuth provider login page."""
        if provider == "google":
            if not settings.GOOGLE_CLIENT_ID:
                raise ValueError("Google OAuth is not configured")
            params = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "online",
            }
            return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
            
        elif provider == "github":
            if not settings.GITHUB_CLIENT_ID:
                raise ValueError("GitHub OAuth is not configured")
            params = {
                "client_id": settings.GITHUB_CLIENT_ID,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
                "scope": "user:email",
                "state": state,
            }
            return f"https://github.com/login/oauth/authorize?{urlencode(params)}"
            
        else:
            raise ValueError(f"Unknown OAuth provider: {provider}")

    async def get_user_info_from_provider(self, provider: str, code: str) -> dict:
        """Exchange auth code for access token and fetch user details from provider."""
        async with httpx.AsyncClient() as client:
            if provider == "google":
                # 1. Exchange code for tokens
                token_url = "https://oauth2.googleapis.com/token"
                token_data = {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                }
                token_resp = await client.post(token_url, data=token_data)
                if token_resp.status_code != 200:
                    logger.error(f"Google token exchange failed: {token_resp.text}")
                    raise ValueError("Failed to retrieve tokens from Google")
                    
                tokens = token_resp.json()
                access_token = tokens.get("access_token")
                
                # 2. Fetch userinfo
                userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
                headers = {"Authorization": f"Bearer {access_token}"}
                userinfo_resp = await client.get(userinfo_url, headers=headers)
                if userinfo_resp.status_code != 200:
                    logger.error(f"Google userinfo fetch failed: {userinfo_resp.text}")
                    raise ValueError("Failed to retrieve profile from Google")
                    
                userinfo = userinfo_resp.json()
                
                # Verify email_verified is true
                email = userinfo.get("email")
                email_verified = userinfo.get("email_verified", False)
                if not email or not email_verified:
                    raise ValueError("Google account email is not verified")
                    
                return {
                    "provider_user_id": str(userinfo.get("sub")),
                    "email": email,
                    "name": userinfo.get("name"),
                }
                
            elif provider == "github":
                # 1. Exchange code for tokens
                token_url = "https://github.com/login/oauth/access_token"
                token_data = {
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_REDIRECT_URI,
                }
                headers = {"Accept": "application/json"}
                token_resp = await client.post(token_url, data=token_data, headers=headers)
                if token_resp.status_code != 200:
                    logger.error(f"GitHub token exchange failed: {token_resp.text}")
                    raise ValueError("Failed to retrieve tokens from GitHub")
                    
                tokens = token_resp.json()
                access_token = tokens.get("access_token")
                if not access_token:
                    logger.error(f"GitHub did not return access_token: {tokens}")
                    raise ValueError("Failed to retrieve tokens from GitHub")

                # 2. Fetch userinfo
                user_url = "https://api.github.com/user"
                user_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": "Auth-Service-Core",
                    "Accept": "application/vnd.github.v3+json",
                }
                user_resp = await client.get(user_url, headers=user_headers)
                if user_resp.status_code != 200:
                    logger.error(f"GitHub profile fetch failed: {user_resp.text}")
                    raise ValueError("Failed to retrieve profile from GitHub")
                    
                profile = user_resp.json()
                provider_user_id = str(profile.get("id"))
                
                # 3. Fetch emails (GitHub emails might be private in default profile)
                email = profile.get("email")
                if not email:
                    emails_url = "https://api.github.com/user/emails"
                    emails_resp = await client.get(emails_url, headers=user_headers)
                    if emails_resp.status_code == 200:
                        emails = emails_resp.json()
                        # Find verified primary email
                        for email_record in emails:
                            if email_record.get("verified") and email_record.get("primary"):
                                email = email_record.get("email")
                                break
                        # Fallback to any verified email if primary isn't verified
                        if not email:
                            for email_record in emails:
                                if email_record.get("verified"):
                                    email = email_record.get("email")
                                    break
                
                if not email:
                    raise ValueError("Verified email address not found on GitHub account")
                    
                return {
                    "provider_user_id": provider_user_id,
                    "email": email,
                    "name": profile.get("login"),
                }
                
            else:
                raise ValueError(f"Unsupported provider: {provider}")

    async def resolve_oauth_user(
        self,
        provider: str,
        provider_user_id: str,
        email: str,
        auth_service: AuthService,
        current_user: User | None = None
    ) -> User:
        """
        Account Linking Strategy:
        1. Find linked account by (provider, provider_user_id)
        2. If logged in (current_user), link this OAuth account to current user (if not already claimed).
        3. If not logged in, resolve by email.
        4. If user exists with same email, link OAuth account.
        5. If user doesn't exist, register a new password-less User and link.
        """
        # 1. Look up OAuth account link
        link = await self.oauth_repo.get_by_provider_id(provider, provider_user_id)
        if link:
            # Check user status
            user = await auth_service.user_repo.get_by_id(link.user_id)
            if not user:
                raise ValueError("User associated with OAuth link not found")
            if not user.is_active:
                raise ValueError("User account is deactivated")
            
            # Security guard: if logged in and it belongs to someone else
            if current_user and current_user.id != user.id:
                raise ValueError("This OAuth account is already linked to another user")
                
            return user

        # 2. If user is currently logged in, link to current user
        if current_user:
            await self.oauth_repo.create(
                user_id=current_user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=email
            )
            logger.info(f"Linked active user {current_user.id} with OAuth provider {provider}")
            
            await auth_service.audit_repo.create(
                action="account_linked",
                user_id=current_user.id,
                metadata_json={"provider": provider, "provider_user_id": provider_user_id}
            )
            return current_user

        # 3. Resolve by email in this tenant
        user = await auth_service.user_repo.get_by_email(email)
        
        if user:
            # Check active
            if not user.is_active:
                raise ValueError("User account is deactivated")
            
            # User exists, link this OAuth provider to the existing account
            await self.oauth_repo.create(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=email
            )
            logger.info(f"Linked existing user {user.id} with OAuth provider {provider}")
        else:
            # 4. User does not exist, create a new user (verified, password-less)
            user = await auth_service.user_repo.create(
                email=email,
                password_hash=None, # OAuth-only users do not have local passwords
                role="user",
                is_verified=True # Email is trusted as verified by OAuth provider
            )
            
            # Create OAuth Account Link
            await self.oauth_repo.create(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=email
            )
            logger.info(f"Created new user {user.id} and linked with OAuth provider {provider}")

        # Create audit log
        await auth_service.audit_repo.create(
            action="account_linked",
            user_id=user.id,
            metadata_json={"provider": provider, "provider_user_id": provider_user_id}
        )

        return user
