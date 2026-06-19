import pytest
import httpx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TEST_API_KEY

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.text = str(json_data)
        
    def json(self):
        return self._json

@pytest.fixture(autouse=True)
def mock_oauth_http(monkeypatch):
    """Mock token exchange and userprofile fetch endpoints for all OAuth providers."""
    original_post = httpx.AsyncClient.post
    original_get = httpx.AsyncClient.get
    
    async def mock_post(self, url, *args, **kwargs):
        url_str = str(url)
        if "oauth2.googleapis.com/token" in url_str:
            return MockResponse({
                "access_token": "mock-google-access-token",
                "id_token": "mock-google-id-token"
            })
        elif "github.com/login/oauth/access_token" in url_str:
            return MockResponse({
                "access_token": "mock-github-access-token"
            })
        elif "discord.com/api/v10/oauth2/token" in url_str:
            return MockResponse({
                "access_token": "mock-discord-access-token"
            })
        elif "appleid.apple.com/auth/token" in url_str:
            import jwt
            fake_id_token = jwt.encode(
                {"sub": "apple_sub_12345", "email": "apple_test_user@example.com"},
                "key",
                algorithm="HS256"
            )
            if isinstance(fake_id_token, bytes):
                fake_id_token = fake_id_token.decode("utf-8")
            return MockResponse({
                "id_token": fake_id_token
            })
        elif "api.twitter.com/2/oauth2/token" in url_str:
            return MockResponse({
                "access_token": "mock-twitter-access-token"
            })
        elif "api.amazon.com/auth/o2/token" in url_str:
            return MockResponse({
                "access_token": "mock-amazon-access-token"
            })
        # Pass-through to original method for local app testing
        return await original_post(self, url, *args, **kwargs)
        
    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        headers = kwargs.get("headers", {})
        auth_header = headers.get("Authorization", "")
        params = kwargs.get("params", {})
        
        if "googleapis.com/oauth2/v3/userinfo" in url_str:
            assert "mock-google-access-token" in auth_header
            return MockResponse({
                "sub": "google_sub_12345",
                "email": "google_test_user@example.com",
                "email_verified": True,
                "name": "Google Test User"
            })
        elif "api.github.com/user/emails" in url_str:
            assert "mock-github-access-token" in auth_header
            return MockResponse([
                {"email": "github_test_user@example.com", "verified": True, "primary": True}
            ])
        elif "api.github.com/user" in url_str:
            assert "mock-github-access-token" in auth_header
            return MockResponse({
                "id": 987654,
                "login": "github_tester",
                "email": None # Trigger emails endpoint
            })
        elif "discord.com/api/users/@me" in url_str:
            assert "mock-discord-access-token" in auth_header
            return MockResponse({
                "id": "discord_sub_12345",
                "email": "discord_test_user@example.com",
                "verified": True,
                "username": "Discord Test User"
            })
        elif "graph.facebook.com/v12.0/oauth/access_token" in url_str:
            return MockResponse({
                "access_token": "mock-facebook-access-token"
            })
        elif "graph.facebook.com/me" in url_str:
            return MockResponse({
                "id": "facebook_sub_12345",
                "email": "facebook_test_user@example.com",
                "name": "Facebook Test User"
            })
        elif "api.twitter.com/2/users/me" in url_str:
            assert "mock-twitter-access-token" in auth_header
            return MockResponse({
                "data": {
                    "id": "twitter_sub_12345",
                    "email": "twitter_test_user@example.com",
                    "name": "Twitter Test User"
                }
            })
        elif "api.amazon.com/user/profile" in url_str:
            assert "mock-amazon-access-token" in auth_header or "bearer mock-amazon-access-token" in auth_header.lower()
            return MockResponse({
                "user_id": "amazon_sub_12345",
                "email": "amazon_test_user@example.com",
                "name": "Amazon Test User"
            })
        # Pass-through to original method for local app testing
        return await original_get(self, url, *args, **kwargs)
        
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

@pytest.mark.asyncio
async def test_oauth_redirect_urls(client: AsyncClient, monkeypatch):
    """Test OAuth authorize redirect URL generation for all supported providers."""
    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "github-id")
    monkeypatch.setattr(settings, "DISCORD_CLIENT_ID", "discord-id")
    monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "apple-id")
    monkeypatch.setattr(settings, "FACEBOOK_CLIENT_ID", "facebook-id")
    monkeypatch.setattr(settings, "TWITTER_CLIENT_ID", "twitter-id")
    monkeypatch.setattr(settings, "AMAZON_CLIENT_ID", "amazon-id")
    monkeypatch.setattr(settings, "ENABLE_DISCORD_OAUTH", True)
    monkeypatch.setattr(settings, "ENABLE_APPLE_OAUTH", True)
    monkeypatch.setattr(settings, "ENABLE_FACEBOOK_OAUTH", True)
    monkeypatch.setattr(settings, "ENABLE_AMAZON_OAUTH", True)
    
    headers = {"X-Api-Key": TEST_API_KEY}
    
    providers = [
        ("google", "accounts.google.com", "google-id"),
        ("github", "github.com/login/oauth", "github-id"),
        ("discord", "discord.com/oauth2/authorize", "discord-id"),
        ("apple", "appleid.apple.com/auth/authorize", "apple-id"),
        ("facebook", "facebook.com/v12.0/dialog/oauth", "facebook-id"),
        ("twitter", "twitter.com/i/oauth2/authorize", "twitter-id"),
        ("amazon", "amazon.com/ap/oa", "amazon-id"),
    ]
    
    for provider, domain, client_id in providers:
        resp = await client.get(f"/api/v1/auth/oauth/{provider}", headers=headers, follow_redirects=False)
        assert resp.status_code == 307
        location = resp.headers["location"]
        assert domain in location
        assert client_id in location

@pytest.mark.asyncio
async def clean_test_user(db_session: AsyncSession, email: str):
    from src.models.user import User
    from src.models.oauth import OAuthAccount
    from src.models.session import Session
    from src.models.token import RefreshToken
    from sqlalchemy import select, delete
    
    res = await db_session.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if user:
        await db_session.execute(delete(OAuthAccount).where(OAuthAccount.user_id == user.id))
        session_res = await db_session.execute(select(Session).where(Session.user_id == user.id))
        sessions = session_res.scalars().all()
        for s in sessions:
            await db_session.execute(delete(RefreshToken).where(RefreshToken.session_id == s.id))
            await db_session.delete(s)
        await db_session.delete(user)
        await db_session.commit()


@pytest.mark.asyncio
async def test_oauth_callback_flow_browser(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """Test full browser-based OAuth callback flow (Google & GitHub)."""
    await clean_test_user(db_session, "google_test_user@example.com")
    await clean_test_user(db_session, "github_test_user@example.com")

    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "github-id")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", "github-secret")
    
    headers = {"X-Api-Key": TEST_API_KEY}
    
    # 1. Initiate Google Login to register state in Redis
    init_resp = await client.get(
        "/api/v1/auth/oauth/google?state=http://localhost:3000/dashboard",
        headers=headers,
        follow_redirects=False
    )
    assert init_resp.status_code == 307
    from urllib.parse import urlparse, parse_qs
    params = parse_qs(urlparse(init_resp.headers["location"]).query)
    internal_state = params["state"][0]

    # 2. Trigger Google Callback using the internal state (will register user and create session)
    g_resp = await client.get(
        f"/api/v1/auth/oauth/google/callback?code=mock-code&state={internal_state}",
        headers=headers,
        follow_redirects=False
    )
    assert g_resp.status_code == 307 # Redirect to target URL
    assert g_resp.headers["location"] == "http://localhost:3000/dashboard"
    
    # Verify browser cookies are set
    cookies = g_resp.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies
    
    # 3. Call /me to verify user was created
    me_resp = await client.get("/api/v1/auth/me", cookies=cookies)
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == "google_test_user@example.com"
    assert me_resp.json()["data"]["is_verified"] is True
    
    # 4. List linked accounts
    link_resp = await client.get("/api/v1/auth/me/linked-accounts", cookies=cookies)
    assert link_resp.status_code == 200
    links = link_resp.json()["data"]
    assert len(links) == 1
    assert links[0]["provider"] == "google"
    assert links[0]["provider_email"] == "google_test_user@example.com"
    
    # 5. Initiate GitHub Login under same browser cookies context
    init_gh = await client.get(
        "/api/v1/auth/oauth/github?state=http://localhost:3000/dashboard",
        headers=headers,
        cookies=cookies,
        follow_redirects=False
    )
    assert init_gh.status_code == 307
    gh_params = parse_qs(urlparse(init_gh.headers["location"]).query)
    gh_internal_state = gh_params["state"][0]

    # 6. Link GitHub to same user by calling GitHub callback under same browser cookies context
    gh_resp = await client.get(
        f"/api/v1/auth/oauth/github/callback?code=mock-code&state={gh_internal_state}",
        headers=headers,
        cookies=cookies,
        follow_redirects=False
    )
    assert gh_resp.status_code == 307
    
    # 7. List linked accounts again - should now have 2 links (Google & GitHub)
    link_resp = await client.get("/api/v1/auth/me/linked-accounts", cookies=cookies)
    links = link_resp.json()["data"]
    assert len(links) == 2
    providers = [l["provider"] for l in links]
    assert "google" in providers
    assert "github" in providers
    
    # 8. Test Security Guard: Unlink GitHub (should succeed because user has Google linked)
    del_resp = await client.delete("/api/v1/auth/me/linked-accounts/github", cookies=cookies)
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True
    
    # Verify only Google link remains
    link_resp = await client.get("/api/v1/auth/me/linked-accounts", cookies=cookies)
    links = link_resp.json()["data"]
    assert len(links) == 1
    assert links[0]["provider"] == "google"
    
    # 9. Test Security Guard: Unlink Google (MUST FAIL because user has no password and no other OAuth provider!)
    del_resp = await client.delete("/api/v1/auth/me/linked-accounts/google", cookies=cookies)
    assert del_resp.status_code == 400
    assert "unlink" in del_resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_2fa_oauth_requires_2fa(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    await clean_test_user(db_session, "google_test_user@example.com")
    
    from src.config import settings
    from src.models.user import User
    from sqlalchemy import select
    from urllib.parse import urlparse, parse_qs

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")

    headers = {"X-Api-Key": TEST_API_KEY}

    # 1. Initiate Google Login to register state in Redis
    init_resp = await client.get(
        "/api/v1/auth/oauth/google?state=http://localhost:3000/dashboard",
        headers=headers,
        follow_redirects=False
    )
    assert init_resp.status_code == 307
    params = parse_qs(urlparse(init_resp.headers["location"]).query)
    internal_state = params["state"][0]

    # 2. Trigger Google Callback to register user
    g_resp = await client.get(
        f"/api/v1/auth/oauth/google/callback?code=mock-code&state={internal_state}",
        headers=headers,
        follow_redirects=False
    )
    assert g_resp.status_code == 307

    # 3. Update user to enable 2FA
    res = await db_session.execute(select(User).where(User.email == "google_test_user@example.com"))
    user = res.scalar_one()
    user.is_two_factor_enabled = True
    user.totp_secret_encrypted = "some_dummy_secret"
    await db_session.commit()

    # 4. Initiate Google Login again to get new internal state
    init_resp2 = await client.get(
        "/api/v1/auth/oauth/google?state=http://localhost:3000/dashboard",
        headers=headers,
        follow_redirects=False
    )
    assert init_resp2.status_code == 307
    params2 = parse_qs(urlparse(init_resp2.headers["location"]).query)
    internal_state2 = params2["state"][0]

    # 5. Call callback again (now requiring 2FA)
    g_resp2 = await client.get(
        f"/api/v1/auth/oauth/google/callback?code=mock-code&state={internal_state2}",
        headers=headers,
        follow_redirects=False
    )
    assert g_resp2.status_code == 307
    location = g_resp2.headers["location"]
    assert "requires_2fa=true" in location
    assert "mfa_token=" in location

    # Cookies should NOT be set
    assert "access_token" not in g_resp2.cookies
    assert "refresh_token" not in g_resp2.cookies


@pytest.mark.asyncio
async def test_oauth_state_csrf_validation(client: AsyncClient, monkeypatch):
    """Test callback rejection when using an invalid/expired state."""
    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")
    
    headers = {"X-Api-Key": TEST_API_KEY}
    
    # Trigger callback with invalid state parameter
    resp = await client.get(
        "/api/v1/auth/oauth/google/callback?code=mock-code&state=invalid-state-value",
        headers=headers,
        follow_redirects=False
    )
    assert resp.status_code == 400
    assert "CSRF" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_oauth_pkce_flow_s256(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """Test OAuth login + callback + token exchange using S256 PKCE."""
    await clean_test_user(db_session, "google_test_user@example.com")
    
    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")
    
    headers = {"X-Api-Key": TEST_API_KEY}
    
    # 1. Initiate login with PKCE challenge (S256)
    # Verifier: dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
    # Challenge: E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
    init_resp = await client.get(
        "/api/v1/auth/oauth/google?state=my-client-state&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256&redirect_uri=http://localhost:3000/callback",
        headers=headers,
        follow_redirects=False
    )
    assert init_resp.status_code == 307
    
    from urllib.parse import urlparse, parse_qs
    params = parse_qs(urlparse(init_resp.headers["location"]).query)
    internal_state = params["state"][0]
    
    # 2. Trigger OAuth callback
    cb_resp = await client.get(
        f"/api/v1/auth/oauth/google/callback?code=mock-code&state={internal_state}",
        headers=headers,
        follow_redirects=False
    )
    assert cb_resp.status_code == 307
    
    # Location should point to redirect_uri with code and client_state
    location = cb_resp.headers["location"]
    assert location.startswith("http://localhost:3000/callback")
    cb_params = parse_qs(urlparse(location).query)
    auth_code = cb_params["code"][0]
    assert cb_params["state"][0] == "my-client-state"
    
    # 3. Exchange auth_code for tokens using code_verifier
    token_resp = await client.post(
        "/api/v1/auth/oauth/token",
        headers=headers,
        json={
            "code": auth_code,
            "code_verifier": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        }
    )
    assert token_resp.status_code == 200
    data = token_resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    
    # 4. Assert single-use: exchanging the same code again must fail
    token_resp_retry = await client.post(
        "/api/v1/auth/oauth/token",
        headers=headers,
        json={
            "code": auth_code,
            "code_verifier": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        }
    )
    assert token_resp_retry.status_code == 400


@pytest.mark.asyncio
async def test_oauth_pkce_invalid_verifier(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """Test that token exchange is rejected if an invalid verifier is provided."""
    await clean_test_user(db_session, "google_test_user@example.com")
    
    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")
    
    headers = {"X-Api-Key": TEST_API_KEY}
    
    # 1. Initiate login
    init_resp = await client.get(
        "/api/v1/auth/oauth/google?state=my-client-state&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256&redirect_uri=http://localhost:3000/callback",
        headers=headers,
        follow_redirects=False
    )
    assert init_resp.status_code == 307
    
    from urllib.parse import urlparse, parse_qs
    params = parse_qs(urlparse(init_resp.headers["location"]).query)
    internal_state = params["state"][0]
    
    # 2. Callback to get auth code
    cb_resp = await client.get(
        f"/api/v1/auth/oauth/google/callback?code=mock-code&state={internal_state}",
        headers=headers,
        follow_redirects=False
    )
    assert cb_resp.status_code == 307
    cb_params = parse_qs(urlparse(cb_resp.headers["location"]).query)
    auth_code = cb_params["code"][0]
    
    # 3. Exchange with invalid verifier
    token_resp = await client.post(
        "/api/v1/auth/oauth/token",
        headers=headers,
        json={
            "code": auth_code,
            "code_verifier": "wrong-verifier-value-here"
        }
    )
    assert token_resp.status_code == 400
    assert "verifier" in token_resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_oauth_flow_new_providers(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """Test full login flow for Discord, Apple, Facebook, Twitter, and Amazon."""
    from src.config import settings
    monkeypatch.setattr(settings, "DISCORD_CLIENT_ID", "discord-id")
    monkeypatch.setattr(settings, "DISCORD_CLIENT_SECRET", "discord-secret")
    monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "apple-id")
    monkeypatch.setattr(settings, "APPLE_CLIENT_SECRET", "apple-secret")
    monkeypatch.setattr(settings, "FACEBOOK_CLIENT_ID", "facebook-id")
    monkeypatch.setattr(settings, "FACEBOOK_CLIENT_SECRET", "facebook-secret")
    monkeypatch.setattr(settings, "TWITTER_CLIENT_ID", "twitter-id")
    monkeypatch.setattr(settings, "TWITTER_CLIENT_SECRET", "twitter-secret")
    monkeypatch.setattr(settings, "AMAZON_CLIENT_ID", "amazon-id")
    monkeypatch.setattr(settings, "AMAZON_CLIENT_SECRET", "amazon-secret")
    monkeypatch.setattr(settings, "ENABLE_DISCORD_OAUTH", True)
    monkeypatch.setattr(settings, "ENABLE_APPLE_OAUTH", True)
    monkeypatch.setattr(settings, "ENABLE_FACEBOOK_OAUTH", True)
    monkeypatch.setattr(settings, "ENABLE_AMAZON_OAUTH", True)
    
    headers = {"X-Api-Key": TEST_API_KEY}
    
    new_providers = [
        ("discord", "discord_test_user@example.com"),
        ("apple", "apple_test_user@example.com"),
        ("facebook", "facebook_test_user@example.com"),
        ("twitter", "twitter_test_user@example.com"),
        ("amazon", "amazon_test_user@example.com"),
    ]
    
    for provider, email in new_providers:
        client.cookies.clear()
        await clean_test_user(db_session, email)
        
        # 1. Initiate login
        init_resp = await client.get(
            f"/api/v1/auth/oauth/{provider}?state=http://localhost:3000/dashboard",
            headers=headers,
            follow_redirects=False
        )
        assert init_resp.status_code == 307
        from urllib.parse import urlparse, parse_qs
        params = parse_qs(urlparse(init_resp.headers["location"]).query)
        internal_state = params["state"][0]
        
        # 2. Trigger callback
        cb_resp = await client.get(
            f"/api/v1/auth/oauth/{provider}/callback?code=mock-code&state={internal_state}",
            headers=headers,
            follow_redirects=False
        )
        assert cb_resp.status_code == 307
        assert cb_resp.headers["location"] == "http://localhost:3000/dashboard"
        
        # Verify browser cookies are set
        cookies = cb_resp.cookies
        assert "access_token" in cookies
        
        # 3. Call /me to verify email matches
        me_resp = await client.get("/api/v1/auth/me", cookies=cookies)
        assert me_resp.status_code == 200
        assert me_resp.json()["data"]["email"] == email


@pytest.mark.asyncio
async def test_oauth_provider_disabled_toggle(client: AsyncClient, monkeypatch):
    """Test that disabled providers are rejected with 400 Bad Request."""
    from src.config import settings
    monkeypatch.setattr(settings, "DISCORD_CLIENT_ID", "discord-id")
    monkeypatch.setattr(settings, "ENABLE_DISCORD_OAUTH", False)
    
    headers = {"X-Api-Key": TEST_API_KEY}
    
    resp = await client.get(
        "/api/v1/auth/oauth/discord?state=http://localhost:3000/dashboard",
        headers=headers,
        follow_redirects=False
    )
    assert resp.status_code == 400
    assert "disabled" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_dynamic_redirect_uri_resolution_from_domain(client: AsyncClient, monkeypatch):
    """Test dynamic redirect URI generation from DOMAIN setting."""
    from src.config import settings
    from src.services.oauth import get_provider_redirect_uri
    
    # 1. Custom domain
    monkeypatch.setattr(settings, "DOMAIN", "auth.mycompany.com")
    uri = get_provider_redirect_uri("google")
    assert uri == "https://auth.mycompany.com/api/v1/auth/oauth/google/callback"
    
    # 2. Localhost
    monkeypatch.setattr(settings, "DOMAIN", "localhost")
    uri = get_provider_redirect_uri("google")
    assert uri == "http://localhost:8000/api/v1/auth/oauth/google/callback"
    
    # 3. Localhost with port
    monkeypatch.setattr(settings, "DOMAIN", "localhost:3000")
    uri = get_provider_redirect_uri("google")
    assert uri == "http://localhost:3000/api/v1/auth/oauth/google/callback"
    
    # 4. Explicit protocol domain
    monkeypatch.setattr(settings, "DOMAIN", "http://my-local-server.test")
    uri = get_provider_redirect_uri("google")
    assert uri == "http://my-local-server.test/api/v1/auth/oauth/google/callback"
    
    # 5. Overridden in settings (should respect override)
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://explicit.uri/callback")
    uri = get_provider_redirect_uri("google")
    assert uri == "http://explicit.uri/callback"
