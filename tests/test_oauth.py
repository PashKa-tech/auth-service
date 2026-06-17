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
    """Mock Google and GitHub token exchange and userprofile fetch endpoints."""
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
        # Pass-through to original method for local app testing
        return await original_post(self, url, *args, **kwargs)
        
    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        headers = kwargs.get("headers", {})
        auth_header = headers.get("Authorization", "")
        
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
        # Pass-through to original method for local app testing
        return await original_get(self, url, *args, **kwargs)
        
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

@pytest.mark.asyncio
async def test_oauth_redirect_urls(client: AsyncClient, monkeypatch):
    """Test OAuth authorize redirect URL generation."""
    # Temporarily set credentials in settings
    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "github-id")
    
    headers = {"X-Api-Key": TEST_API_KEY}
    
    # 1. Google
    resp = await client.get("/api/v1/auth/oauth/google", headers=headers, follow_redirects=False)
    assert resp.status_code == 307  # FastAPI Redirect status code
    assert "accounts.google.com" in resp.headers["location"]
    assert "google-id" in resp.headers["location"]
    
    # 2. GitHub
    resp = await client.get("/api/v1/auth/oauth/github", headers=headers, follow_redirects=False)
    assert resp.status_code == 307
    assert "github.com/login/oauth" in resp.headers["location"]
    assert "github-id" in resp.headers["location"]

@pytest.mark.asyncio
async def test_oauth_callback_flow_browser(client: AsyncClient, monkeypatch):
    """Test full browser-based OAuth callback flow (Google & GitHub)."""
    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "github-id")
    monkeypatch.setattr(settings, "GITHUB_CLIENT_SECRET", "github-secret")
    
    headers = {"X-Api-Key": TEST_API_KEY}
    
    # 1. Trigger Google Callback (will register user and create session)
    g_resp = await client.get(
        "/api/v1/auth/oauth/google/callback?code=mock-code&state=http://localhost:3000/dashboard",
        headers=headers,
        follow_redirects=False
    )
    assert g_resp.status_code == 307 # Redirect to target URL
    assert g_resp.headers["location"] == "http://localhost:3000/dashboard"
    
    # Verify browser cookies are set
    cookies = g_resp.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies
    
    # 2. Call /me to verify user was created
    me_resp = await client.get("/api/v1/auth/me", cookies=cookies)
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == "google_test_user@example.com"
    assert me_resp.json()["data"]["is_verified"] is True
    
    # 3. List linked accounts
    link_resp = await client.get("/api/v1/auth/me/linked-accounts", cookies=cookies)
    assert link_resp.status_code == 200
    links = link_resp.json()["data"]
    assert len(links) == 1
    assert links[0]["provider"] == "google"
    assert links[0]["provider_email"] == "google_test_user@example.com"
    
    # 4. Link GitHub to same user by calling GitHub callback under same browser cookies context
    gh_resp = await client.get(
        "/api/v1/auth/oauth/github/callback?code=mock-code&state=http://localhost:3000/dashboard",
        headers=headers,
        cookies=cookies,
        follow_redirects=False
    )
    assert gh_resp.status_code == 307
    
    # 5. List linked accounts again - should now have 2 links (Google & GitHub)
    link_resp = await client.get("/api/v1/auth/me/linked-accounts", cookies=cookies)
    links = link_resp.json()["data"]
    assert len(links) == 2
    providers = [l["provider"] for l in links]
    assert "google" in providers
    assert "github" in providers
    
    # 6. Test Security Guard: Unlink GitHub (should succeed because user has Google linked)
    del_resp = await client.delete("/api/v1/auth/me/linked-accounts/github", cookies=cookies)
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True
    
    # Verify only Google link remains
    link_resp = await client.get("/api/v1/auth/me/linked-accounts", cookies=cookies)
    links = link_resp.json()["data"]
    assert len(links) == 1
    assert links[0]["provider"] == "google"
    
    # 7. Test Security Guard: Unlink Google (MUST FAIL because user has no password and no other OAuth provider!)
    del_resp = await client.delete("/api/v1/auth/me/linked-accounts/google", cookies=cookies)
    assert del_resp.status_code == 400
    assert "unlink" in del_resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_2fa_oauth_requires_2fa(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from src.config import settings
    from src.models.user import User
    from sqlalchemy import select

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "google-secret")

    headers = {"X-Api-Key": TEST_API_KEY}

    # 1. Trigger Google Callback to register user
    g_resp = await client.get(
        "/api/v1/auth/oauth/google/callback?code=mock-code&state=http://localhost:3000/dashboard",
        headers=headers,
        follow_redirects=False
    )
    assert g_resp.status_code == 307

    # 2. Update user to enable 2FA
    res = await db_session.execute(select(User).where(User.email == "google_test_user@example.com"))
    user = res.scalar_one()
    user.is_two_factor_enabled = True
    user.totp_secret_encrypted = "some_dummy_secret"
    await db_session.commit()

    # 3. Call callback again (now requiring 2FA)
    g_resp2 = await client.get(
        "/api/v1/auth/oauth/google/callback?code=mock-code&state=http://localhost:3000/dashboard",
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
