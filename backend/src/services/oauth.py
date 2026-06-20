import uuid
import httpx
from urllib.parse import urlencode
from src.config import settings
from src.core.logging import logger
from src.repositories.oauth import OAuthRepository
from src.services.auth import AuthService
from src.models.user import User
from dataclasses import dataclass

@dataclass
class OAuthUserInfo:
    email: str
    provider_id: str

def get_normalized_base_url() -> str:
    domain = settings.DOMAIN
    if not domain.startswith(("http://", "https://")):
        if "localhost" in domain or ":" in domain:
            if domain == "localhost":
                domain = "localhost:8000"
            domain = f"http://{domain}"
        else:
            domain = f"https://{domain}"
    return domain.rstrip("/")

def get_provider_redirect_uri(provider: str) -> str:
    override = getattr(settings, f"{provider.upper()}_REDIRECT_URI", None)
    if override:
        return override
    base_url = get_normalized_base_url()
    return f"{base_url}{settings.API_V1_STR}/oauth/{provider}/callback"

class OAuthService:
    def __init__(self, oauth_repo: OAuthRepository):
        self.oauth_repo = oauth_repo
        self.tenant_id = oauth_repo.tenant_id

    def get_authorization_url(self, provider: str, state: str, extra_params: dict | None = None) -> str:
        """Generate redirect URL to OAuth provider login page."""
        provider_upper = provider.upper()
        
        # Check toggle
        enabled = getattr(settings, f"ENABLE_{provider_upper}_OAUTH", False)
        if not enabled:
            raise ValueError(f"OAuth provider {provider} is disabled")
            
        client_id = getattr(settings, f"{provider_upper}_CLIENT_ID", None)
        if not client_id:
            raise ValueError(f"OAuth provider {provider} is not configured")
            
        redirect_uri = get_provider_redirect_uri(provider)
        
        if provider == "google":
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "online",
            }
            return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
            
        elif provider == "github":
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "user:email",
                "state": state,
            }
            return f"https://github.com/login/oauth/authorize?{urlencode(params)}"
            
        elif provider == "discord":
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "identify email",
                "state": state,
            }
            return f"https://discord.com/oauth2/authorize?{urlencode(params)}"
            
        elif provider == "apple":
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "name email",
                "response_mode": "query",
                "state": state,
            }
            return f"https://appleid.apple.com/auth/authorize?{urlencode(params)}"
            
        elif provider == "facebook":
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "public_profile email",
                "state": state,
            }
            return f"https://www.facebook.com/v12.0/dialog/oauth?{urlencode(params)}"
            
        elif provider == "twitter":
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "users.read tweet.read email.read",
                "state": state,
            }
            if extra_params:
                if "code_challenge" in extra_params:
                    params["code_challenge"] = extra_params["code_challenge"]
                if "code_challenge_method" in extra_params:
                    params["code_challenge_method"] = extra_params["code_challenge_method"]
            return f"https://twitter.com/i/oauth2/authorize?{urlencode(params)}"
            
        elif provider == "amazon":
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "profile",
                "state": state,
                "response_type": "code",
            }
            return f"https://www.amazon.com/ap/oa?{urlencode(params)}"
            
        else:
            raise ValueError(f"Unknown OAuth provider: {provider}")

    async def get_user_info_from_provider(self, provider: str, code: str, redirect_uri: str | None = None, code_verifier: str | None = None) -> OAuthUserInfo:
        """Exchange auth code for access token and fetch user details from provider."""
        provider_upper = provider.upper()
        enabled = getattr(settings, f"ENABLE_{provider_upper}_OAUTH", False)
        if not enabled:
            raise ValueError(f"OAuth provider {provider} is disabled")
            
        if not redirect_uri:
            redirect_uri = get_provider_redirect_uri(provider)
            
        async with httpx.AsyncClient() as client:
            if provider == "google":
                return await self._get_google_user_info(client, code, redirect_uri)
            elif provider == "github":
                return await self._get_github_user_info(client, code, redirect_uri)
            elif provider == "discord":
                return await self._get_discord_user_info(client, code, redirect_uri)
            elif provider == "apple":
                return await self._get_apple_user_info(client, code, redirect_uri)
            elif provider == "facebook":
                return await self._get_facebook_user_info(client, code, redirect_uri)
            elif provider == "twitter":
                return await self._get_twitter_user_info(client, code, redirect_uri, code_verifier)
            elif provider == "amazon":
                return await self._get_amazon_user_info(client, code, redirect_uri)
            else:
                raise ValueError(f"Unsupported provider: {provider}")

    async def _get_google_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str) -> OAuthUserInfo:
        # 1. Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
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
            
        return OAuthUserInfo(
            provider_id=str(userinfo.get("sub")),
            email=email,
        )

    async def _get_github_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str) -> OAuthUserInfo:
        # 1. Exchange code for token
        token_url = "https://github.com/login/oauth/access_token"
        headers = {"Accept": "application/json"}
        token_data = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        token_resp = await client.post(token_url, data=token_data, headers=headers)
        if token_resp.status_code != 200:
            logger.error(f"GitHub token exchange failed: {token_resp.text}")
            raise ValueError("Failed to exchange code for token")
            
        token_json = token_resp.json()
        if "error" in token_json:
            raise ValueError(f"GitHub OAuth error: {token_json.get('error_description', token_json['error'])}")
            
        access_token = token_json["access_token"]
        
        # 2. Get user info
        user_url = "https://api.github.com/user"
        user_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        user_resp = await client.get(user_url, headers=user_headers)
        if user_resp.status_code != 200:
            logger.error(f"GitHub profile fetch failed: {user_resp.text}")
            raise ValueError("Failed to retrieve profile from GitHub")
            
        profile = user_resp.json()
        provider_user_id = str(profile.get("id"))
        
        # 3. Fetch emails
        email = profile.get("email")
        if not email:
            emails_url = "https://api.github.com/user/emails"
            emails_resp = await client.get(emails_url, headers=user_headers)
            if emails_resp.status_code == 200:
                emails = emails_resp.json()
                for email_record in emails:
                    if email_record.get("verified") and email_record.get("primary"):
                        email = email_record.get("email")
                        break
                if not email:
                    for email_record in emails:
                        if email_record.get("verified"):
                            email = email_record.get("email")
                            break
        
        if not email:
            raise ValueError("Verified email address not found on GitHub account")
            
        return OAuthUserInfo(
            provider_id=provider_user_id,
            email=email,
        )

    async def _get_discord_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str) -> OAuthUserInfo:
        token_url = "https://discord.com/api/v10/oauth2/token"
        token_data = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_resp = await client.post(token_url, data=token_data, headers=headers)
        if token_resp.status_code != 200:
            logger.error(f"Discord token exchange failed: {token_resp.text}")
            raise ValueError("Failed to retrieve tokens from Discord")
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        
        userinfo_url = "https://discord.com/api/users/@me"
        userinfo_resp = await client.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
        if userinfo_resp.status_code != 200:
            logger.error(f"Discord userinfo fetch failed: {userinfo_resp.text}")
            raise ValueError("Failed to retrieve profile from Discord")
        userinfo = userinfo_resp.json()
        email = userinfo.get("email")
        if not email or not userinfo.get("verified", False):
            raise ValueError("Discord account email is not verified")
        return OAuthUserInfo(
            provider_id=str(userinfo.get("id")),
            email=email,
        )

    async def _get_apple_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str) -> OAuthUserInfo:
        token_url = "https://appleid.apple.com/auth/token"
        token_data = {
            "client_id": settings.APPLE_CLIENT_ID,
            "client_secret": settings.APPLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        token_resp = await client.post(token_url, data=token_data)
        if token_resp.status_code != 200:
            logger.error(f"Apple token exchange failed: {token_resp.text}")
            raise ValueError("Failed to retrieve tokens from Apple")
        tokens = token_resp.json()
        id_token = tokens.get("id_token")
        if not id_token:
            raise ValueError("Apple did not return id_token")
        
        import jwt
        decoded = jwt.decode(id_token, options={"verify_signature": False})
        email = decoded.get("email")
        if not email:
            raise ValueError("Apple id_token does not contain email")
        return OAuthUserInfo(
            provider_id=str(decoded.get("sub")),
            email=email,
        )

    async def _get_facebook_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str) -> OAuthUserInfo:
        token_url = "https://graph.facebook.com/v12.0/oauth/access_token"
        token_params = {
            "client_id": settings.FACEBOOK_CLIENT_ID,
            "client_secret": settings.FACEBOOK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        token_resp = await client.get(token_url, params=token_params)
        if token_resp.status_code != 200:
            logger.error(f"Facebook token exchange failed: {token_resp.text}")
            raise ValueError("Failed to retrieve tokens from Facebook")
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        
        userinfo_url = "https://graph.facebook.com/me?fields=id,email,name"
        userinfo_resp = await client.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
        if userinfo_resp.status_code != 200:
            logger.error(f"Facebook userinfo fetch failed: {userinfo_resp.text}")
            raise ValueError("Failed to retrieve profile from Facebook")
        userinfo = userinfo_resp.json()
        email = userinfo.get("email")
        if not email:
            raise ValueError("Facebook account does not have a verified email address")
        return OAuthUserInfo(
            provider_id=str(userinfo.get("id")),
            email=email,
        )

    async def _get_twitter_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, code_verifier: str | None) -> OAuthUserInfo:
        token_url = "https://api.twitter.com/2/oauth2/token"
        token_data = {
            "client_id": settings.TWITTER_CLIENT_ID,
            "client_secret": settings.TWITTER_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        import base64
        auth_str = f"{settings.TWITTER_CLIENT_ID}:{settings.TWITTER_CLIENT_SECRET or ''}"
        b64_auth = base64.b64encode(auth_str.encode("ascii")).decode("ascii")
        headers = {"Authorization": f"Basic {b64_auth}"}
        token_resp = await client.post(token_url, data=token_data, headers=headers)
        if token_resp.status_code != 200:
            logger.error(f"Twitter token exchange failed: {token_resp.text}")
            raise ValueError("Failed to retrieve tokens from Twitter")
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        
        userinfo_url = "https://api.twitter.com/2/users/me"
        userinfo_params = {"user.fields": "email"}
        userinfo_resp = await client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=userinfo_params
        )
        if userinfo_resp.status_code != 200:
            logger.error(f"Twitter userinfo fetch failed: {userinfo_resp.text}")
            raise ValueError("Failed to retrieve profile from Twitter")
        userinfo = userinfo_resp.json()
        data_block = userinfo.get("data", {})
        email = data_block.get("email")
        if not email:
            raise ValueError("Twitter account does not have an email address")
        return OAuthUserInfo(
            provider_id=str(data_block.get("id")),
            email=email,
        )

    async def _get_amazon_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str) -> OAuthUserInfo:
        token_url = "https://api.amazon.com/auth/o2/token"
        token_data = {
            "client_id": settings.AMAZON_CLIENT_ID,
            "client_secret": settings.AMAZON_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        token_resp = await client.post(token_url, data=token_data)
        if token_resp.status_code != 200:
            logger.error(f"Amazon token exchange failed: {token_resp.text}")
            raise ValueError("Failed to retrieve tokens from Amazon")
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        
        userinfo_url = "https://api.amazon.com/user/profile"
        userinfo_resp = await client.get(userinfo_url, headers={"Authorization": f"bearer {access_token}"})
        if userinfo_resp.status_code != 200:
            logger.error(f"Amazon userinfo fetch failed: {userinfo_resp.text}")
            raise ValueError("Failed to retrieve profile from Amazon")
        userinfo = userinfo_resp.json()
        email = userinfo.get("email")
        if not email:
            raise ValueError("Amazon account does not have an email address")
        return OAuthUserInfo(
            provider_id=str(userinfo.get("user_id")),
            email=email,
        )

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
