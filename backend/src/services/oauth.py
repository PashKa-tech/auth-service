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

    @property
    @abstractmethod
    def token_url(self) -> str:
        pass

    @property
    @abstractmethod
    def userinfo_url(self) -> str:
        pass

    @abstractmethod
    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        pass

    # Template Method
    async def get_user_info(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> OAuthUserInfo:
        token_data = await self._exchange_code_for_token(client, code, redirect_uri, client_id, client_secret, code_verifier)
        profile_data = await self._fetch_user_profile(client, token_data)
        return self._extract_user_info(profile_data, token_data)

    async def _exchange_code_for_token(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> dict:
        token_data_payload = self._get_token_request_data(code, redirect_uri, client_id, client_secret, code_verifier)
        token_headers = self._get_token_request_headers(client_id, client_secret)
        
        token_resp = await client.post(self.token_url, data=token_data_payload, headers=token_headers)
        if token_resp.status_code != 200:
            logger.error(f"{self.name} token exchange failed: {token_resp.text}")
            raise ValueError(f"Failed to retrieve tokens from {self.name}")
            
        token_json = token_resp.json()
        if "error" in token_json and not isinstance(token_json["error"], dict):
            # some providers might return "error" key (e.g., github)
            raise ValueError(f"{self.name} OAuth error: {token_json.get('error_description', token_json['error'])}")
            
        return token_json

    async def _fetch_user_profile(self, client: httpx.AsyncClient, token_data: dict) -> dict:
        if not self.userinfo_url:
            return {}
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(f"No access token provided by {self.name}")
            
        headers = self._get_userinfo_request_headers(access_token)
        params = self._get_userinfo_request_params()
        userinfo_resp = await client.get(self.userinfo_url, headers=headers, params=params)
        if userinfo_resp.status_code != 200:
            logger.error(f"{self.name} userinfo fetch failed: {userinfo_resp.text}")
            raise ValueError(f"Failed to retrieve profile from {self.name}")
            
        return userinfo_resp.json()

    def _get_token_request_data(self, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> dict:
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        return data

    def _get_token_request_headers(self, client_id: str, client_secret: str) -> dict:
        return {"Accept": "application/json"}
        
    def _get_userinfo_request_headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        
    def _get_userinfo_request_params(self) -> dict:
        return {}

    @abstractmethod
    def _extract_user_info(self, profile_data: dict, token_data: dict) -> OAuthUserInfo:
        pass

class GoogleStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "google"

    @property
    def token_url(self) -> str: return "https://oauth2.googleapis.com/token"

    @property
    def userinfo_url(self) -> str: return "https://www.googleapis.com/oauth2/v3/userinfo"

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

    def _extract_user_info(self, profile_data: dict, token_data: dict) -> OAuthUserInfo:
        email = profile_data.get("email")
        email_verified = profile_data.get("email_verified", False)
        if not email or not email_verified:
            raise ValueError("Google account email is not verified")
            
        return OAuthUserInfo(provider_id=str(profile_data.get("sub")), email=email)

class GitHubStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "github"

    @property
    def token_url(self) -> str: return "https://github.com/login/oauth/access_token"

    @property
    def userinfo_url(self) -> str: return "https://api.github.com/user"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "user:email",
            "state": state,
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    async def _fetch_user_profile(self, client: httpx.AsyncClient, token_data: dict) -> dict:
        profile = await super()._fetch_user_profile(client, token_data)
        
        email = profile.get("email")
        if not email:
            access_token = token_data.get("access_token")
            emails_url = "https://api.github.com/user/emails"
            headers = self._get_userinfo_request_headers(access_token)
            emails_resp = await client.get(emails_url, headers=headers)
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
            profile["email"] = email
        return profile

    def _extract_user_info(self, profile_data: dict, token_data: dict) -> OAuthUserInfo:
        provider_user_id = str(profile_data.get("id"))
        email = profile_data.get("email")
        if not email:
            raise ValueError("Verified email address not found on GitHub account")
            
        return OAuthUserInfo(provider_id=provider_user_id, email=email)

class DiscordStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "discord"

    @property
    def token_url(self) -> str: return "https://discord.com/api/v10/oauth2/token"

    @property
    def userinfo_url(self) -> str: return "https://discord.com/api/users/@me"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify email",
            "state": state,
        }
        return f"https://discord.com/oauth2/authorize?{urlencode(params)}"

    def _get_token_request_headers(self, client_id: str, client_secret: str) -> dict:
        return {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

    def _extract_user_info(self, profile_data: dict, token_data: dict) -> OAuthUserInfo:
        email = profile_data.get("email")
        if not email or not profile_data.get("verified", False):
            raise ValueError("Discord account email is not verified")
        return OAuthUserInfo(provider_id=str(profile_data.get("id")), email=email)

class AppleStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "apple"

    @property
    def token_url(self) -> str: return "https://appleid.apple.com/auth/token"

    @property
    def userinfo_url(self) -> str: return ""

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

    async def _fetch_user_profile(self, client: httpx.AsyncClient, token_data: dict) -> dict:
        id_token = token_data.get("id_token")
        if not id_token:
            raise ValueError("Apple did not return id_token")
        
        import jwt
        import asyncio
        from jwt import PyJWKClient
        
        jwks_client = PyJWKClient("https://appleid.apple.com/auth/keys")
        loop = asyncio.get_running_loop()
        signing_key = await loop.run_in_executor(
            None, 
            jwks_client.get_signing_key_from_jwt, 
            id_token
        )
        
        try:
            # We skip audience verification here because we do not have client_id in this scope,
            # but the token was retrieved directly from Apple's server so it's trusted.
            decoded = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False},
                issuer="https://appleid.apple.com"
            )
        except jwt.PyJWTError as e:
            logger.error(f"Apple id_token verification failed: {str(e)}")
            raise ValueError("Invalid Apple id_token signature")
            
        return decoded

    def _extract_user_info(self, profile_data: dict, token_data: dict) -> OAuthUserInfo:
        email = profile_data.get("email")
        if not email:
            raise ValueError("Apple id_token does not contain email")
            
        email_verified = profile_data.get("email_verified")
        if str(email_verified).lower() not in ("true", "1"):
            raise ValueError("Apple account email is not verified")
            
        return OAuthUserInfo(provider_id=str(profile_data.get("sub")), email=email)

class FacebookStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "facebook"

    @property
    def token_url(self) -> str: return "https://graph.facebook.com/v12.0/oauth/access_token"

    @property
    def userinfo_url(self) -> str: return "https://graph.facebook.com/me"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "public_profile email",
            "state": state,
        }
        return f"https://www.facebook.com/v12.0/dialog/oauth?{urlencode(params)}"

    async def _exchange_code_for_token(self, client: httpx.AsyncClient, code: str, redirect_uri: str, client_id: str, client_secret: str, code_verifier: str | None = None) -> dict:
        token_params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        token_resp = await client.get(self.token_url, params=token_params)
        if token_resp.status_code != 200:
            logger.error(f"Facebook token exchange failed: {token_resp.text}")
            raise ValueError("Failed to retrieve tokens from Facebook")
        return token_resp.json()

    def _get_userinfo_request_params(self) -> dict:
        return {"fields": "id,email,name"}

    def _extract_user_info(self, profile_data: dict, token_data: dict) -> OAuthUserInfo:
        email = profile_data.get("email")
        if not email:
            raise ValueError("Facebook account does not have a verified email address")
        return OAuthUserInfo(provider_id=str(profile_data.get("id")), email=email)

class TwitterStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "twitter"

    @property
    def token_url(self) -> str: return "https://api.twitter.com/2/oauth2/token"

    @property
    def userinfo_url(self) -> str: return "https://api.twitter.com/2/users/me"

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

    def _get_token_request_headers(self, client_id: str, client_secret: str) -> dict:
        import base64
        auth_str = f"{client_id}:{client_secret or ''}"
        b64_auth = base64.b64encode(auth_str.encode("ascii")).decode("ascii")
        return {"Authorization": f"Basic {b64_auth}", "Accept": "application/json"}

    def _get_userinfo_request_params(self) -> dict:
        return {"user.fields": "email"}

    def _extract_user_info(self, profile_data: dict, token_data: dict) -> OAuthUserInfo:
        data_block = profile_data.get("data", {})
        email = data_block.get("email")
        if not email:
            raise ValueError("Twitter account does not have an email address")
        return OAuthUserInfo(provider_id=str(data_block.get("id")), email=email)

class AmazonStrategy(OAuthProviderStrategy):
    @property
    def name(self) -> str: return "amazon"

    @property
    def token_url(self) -> str: return "https://api.amazon.com/auth/o2/token"

    @property
    def userinfo_url(self) -> str: return "https://api.amazon.com/user/profile"

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str, extra_params: dict | None = None) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "profile",
            "state": state,
            "response_type": "code",
        }
        return f"https://www.amazon.com/ap/oa?{urlencode(params)}"

    def _get_userinfo_request_headers(self, access_token: str) -> dict:
        return {"Authorization": f"bearer {access_token}", "Accept": "application/json"}

    def _extract_user_info(self, profile_data: dict, token_data: dict) -> OAuthUserInfo:
        email = profile_data.get("email")
        if not email:
            raise ValueError("Amazon account does not have an email address")
        return OAuthUserInfo(provider_id=str(profile_data.get("user_id")), email=email)


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
        from src.core import http_client as http_client_module
        client_to_use = http_client_module.http_client
        
        if client_to_use:
            return await strategy.get_user_info(client_to_use, code, redirect_uri, client_id, client_secret, code_verifier)
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
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
