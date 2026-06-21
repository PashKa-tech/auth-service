import uuid
import httpx
from urllib.parse import urlencode
from abc import ABC, abstractmethod
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

class OAuthProviderStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        pass

    @abstractmethod
    async def get_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> OAuthUserInfo:
        pass

class GoogleStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "google"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    async def get_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> OAuthUserInfo:
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
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
        
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_resp = await client.get(userinfo_url, headers=headers)
        if userinfo_resp.status_code != 200:
            logger.error(f"Google userinfo fetch failed: {userinfo_resp.text}")
            raise ValueError("Failed to retrieve profile from Google")
            
        userinfo = userinfo_resp.json()
        
        email = userinfo.get("email")
        email_verified = userinfo.get("email_verified", False)
        if not email or not email_verified:
            raise ValueError("Google account email is not verified")
            
        return OAuthUserInfo(provider_id=str(userinfo.get("sub")), email=email)

class GitHubStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "github"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "user:email",
            "state": state,
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    async def get_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> OAuthUserInfo:
        token_url = "https://github.com/login/oauth/access_token"
        headers = {"Accept": "application/json"}
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
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
        
        user_url = "https://api.github.com/user"
        user_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        user_resp = await client.get(user_url, headers=user_headers)
        if user_resp.status_code != 200:
            logger.error(f"GitHub profile fetch failed: {user_resp.text}")
            raise ValueError("Failed to retrieve profile from GitHub")
            
        profile = user_resp.json()
        provider_user_id = str(profile.get("id"))
        
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
            
        return OAuthUserInfo(provider_id=provider_user_id, email=email)

class DiscordStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "discord"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify email",
            "state": state,
        }
        return f"https://discord.com/oauth2/authorize?{urlencode(params)}"

    async def get_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> OAuthUserInfo:
        token_url = "https://discord.com/api/v10/oauth2/token"
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
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
        return OAuthUserInfo(provider_id=str(userinfo.get("id")), email=email)

class AppleStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "apple"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "name email",
            "response_mode": "query",
            "state": state,
        }
        return f"https://appleid.apple.com/auth/authorize?{urlencode(params)}"

    async def get_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> OAuthUserInfo:
        token_url = "https://appleid.apple.com/auth/token"
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
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
        return OAuthUserInfo(provider_id=str(decoded.get("sub")), email=email)

class FacebookStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "facebook"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "public_profile email",
            "state": state,
        }
        return f"https://www.facebook.com/v12.0/dialog/oauth?{urlencode(params)}"

    async def get_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> OAuthUserInfo:
        token_url = "https://graph.facebook.com/v12.0/oauth/access_token"
        token_params = {
            "client_id": client_id,
            "client_secret": client_secret,
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
        return OAuthUserInfo(provider_id=str(userinfo.get("id")), email=email)

class TwitterStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "twitter"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
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

    async def get_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> OAuthUserInfo:
        token_url = "https://api.twitter.com/2/oauth2/token"
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        import base64
        auth_str = f"{client_id}:{client_secret or ''}"
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
        return OAuthUserInfo(provider_id=str(data_block.get("id")), email=email)

class AmazonStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "amazon"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "profile",
            "state": state,
            "response_type": "code",
        }
        return f"https://www.amazon.com/ap/oa?{urlencode(params)}"

    async def get_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> OAuthUserInfo:
        token_url = "https://api.amazon.com/auth/o2/token"
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
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
        return OAuthUserInfo(provider_id=str(userinfo.get("user_id")), email=email)


class OAuthService:
    def __init__(self, oauth_repo: OAuthRepository):
        self.oauth_repo = oauth_repo
        self.tenant_id = oauth_repo.tenant_id
        self.strategies: dict[str, OAuthProviderStrategy] = {
            "google": GoogleStrategy(),
            "github": GitHubStrategy(),
            "discord": DiscordStrategy(),
            "apple": AppleStrategy(),
            "facebook": FacebookStrategy(),
            "twitter": TwitterStrategy(),
            "amazon": AmazonStrategy(),
        }

    def _get_strategy(self, provider: str) -> OAuthProviderStrategy:
        strategy = self.strategies.get(provider.lower())
        if not strategy:
            raise ValueError(f"Unknown or unsupported OAuth provider: {provider}")
        return strategy

    def get_authorization_url(self, provider: str, state: str, extra_params: dict | None = None) -> str:
        """Generate redirect URL to OAuth provider login page."""
        provider_upper = provider.upper()
        enabled = getattr(settings, f"ENABLE_{provider_upper}_OAUTH", False)
        if not enabled:
            raise ValueError(f"OAuth provider {provider} is disabled")
            
        client_id = getattr(settings, f"{provider_upper}_CLIENT_ID", None)
        if not client_id:
            raise ValueError(f"OAuth provider {provider} is not configured")
            
        redirect_uri = get_provider_redirect_uri(provider)
        strategy = self._get_strategy(provider)
        return strategy.get_authorization_url(client_id, redirect_uri, state, extra_params)

    async def get_user_info_from_provider(self, provider: str, code: str, redirect_uri: str | None = None, code_verifier: str | None = None) -> OAuthUserInfo:
        """Exchange auth code for access token and fetch user details from provider."""
        provider_upper = provider.upper()
        enabled = getattr(settings, f"ENABLE_{provider_upper}_OAUTH", False)
        if not enabled:
            raise ValueError(f"OAuth provider {provider} is disabled")
            
        client_id = getattr(settings, f"{provider_upper}_CLIENT_ID", None)
        client_secret = getattr(settings, f"{provider_upper}_CLIENT_SECRET", None)
        if not client_id:
            raise ValueError(f"OAuth provider {provider} is not configured")
            
        if not redirect_uri:
            redirect_uri = get_provider_redirect_uri(provider)
            
        strategy = self._get_strategy(provider)
        async with httpx.AsyncClient() as client:
            return await strategy.get_user_info(client, code, redirect_uri, client_id, client_secret, code_verifier)

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
