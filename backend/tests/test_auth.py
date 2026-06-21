import pytest
from httpx import AsyncClient
from tests.conftest import TEST_API_KEY, TEST_TENANT_ID

@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient, verify_user):
    """Test healthcheck endpoints."""
    # Liveness
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    
    # Readiness (will check DB and mock Redis)
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["details"]["database"] == "ok"
    assert data["details"]["redis"] == "ok"

@pytest.mark.asyncio
async def test_user_registration_validation(client: AsyncClient, verify_user):
    """Test user registration validations (missing tenant, short password)."""
    # 1. Register without X-Api-Key
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "securepassword123"}
    )
    assert resp.status_code == 401
    assert resp.json()["success"] is False
    
    # 2. Register with invalid password length (too short)
    headers = {"X-Api-Key": TEST_API_KEY}
    resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": "test@example.com", "password": "short"}
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False
    assert "validation" in resp.json()["error"]["code"].lower()

@pytest.mark.asyncio
async def test_auth_full_flow_browser(client: AsyncClient, verify_user):
    """Test complete authentication flow for browser clients (using cookies)."""
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "browser_user@example.com"
    password = "SuperPassword123!"
    
    # 1. Register User
    reg_resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201
    assert reg_resp.json()["success"] is True
    assert reg_resp.json()["data"]["email"] == email
    await verify_user(email)
    
    # 2. Attempt duplicate registration
    reg_dup = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_dup.status_code == 409
    
    # 3. Login User (Browser - default)
    login_resp = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["success"] is True
    # Verify cookies are set
    cookies = login_resp.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies
    
    # 4. Fetch /me (authorized route, uses access_token cookie)
    me_resp = await client.get("/api/v1/auth/me", cookies=cookies)
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == email
    
    # 5. List Active Sessions
    sess_resp = await client.get("/api/v1/auth/sessions", cookies=cookies)
    assert sess_resp.status_code == 200
    sessions = sess_resp.json()["data"]
    assert len(sessions) == 1
    session_id = sessions[0]["id"]
    
    # 6. Refresh Tokens (Rotation)
    # Grab the current refresh token
    orig_refresh = cookies.get("refresh_token")
    
    ref_resp = await client.post("/api/v1/auth/refresh", cookies=cookies)
    assert ref_resp.status_code == 200
    assert ref_resp.json()["success"] is True
    
    # Verify cookies have rotated
    new_cookies = ref_resp.cookies
    assert new_cookies.get("refresh_token") != orig_refresh
    
    # 7. Check Security: Reuse Attack Protection!
    # Try to reuse the original refresh token which is now rotated (revoked)
    reuse_cookies = cookies # has orig_refresh
    client.cookies.clear() # Prevent httpx from silently using the rotated token from its internal jar
    reuse_resp = await client.post("/api/v1/auth/refresh", cookies=reuse_cookies)
    assert reuse_resp.status_code == 401
    assert "reuse" in reuse_resp.json()["error"]["message"].lower()
    
    # Verify that reuse attack revoked the session family
    # The new_cookies (which was valid before reuse attempt) should now be invalid!
    me_after_attack = await client.get("/api/v1/auth/me", cookies=new_cookies)
    assert me_after_attack.status_code == 401
    
@pytest.mark.asyncio
async def test_auth_flow_mobile(client: AsyncClient, verify_user):
    """Test mobile client flow using Headers instead of Cookies."""
    headers = {
        "X-Api-Key": TEST_API_KEY,
        "X-Client-Type": "mobile" # Signal mobile client
    }
    email = "mobile_user@example.com"
    password = "SuperPassword123!"
    
    # 1. Register User
    reg_resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201
    
    # 2. Login User
    login_resp = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    data = login_resp.json()["data"]
    
    # Verify tokens are in body and NOT cookies
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(login_resp.cookies) == 0
    
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]
    
    # 3. Request /me using Bearer header
    me_headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = await client.get("/api/v1/auth/me", headers=me_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == email
    
    # 4. Refresh using X-Refresh-Token header
    ref_headers = {
        "X-Client-Type": "mobile",
        "X-Refresh-Token": refresh_token
    }
    ref_resp = await client.post("/api/v1/auth/refresh", headers=ref_headers)
    assert ref_resp.status_code == 200
    ref_data = ref_resp.json()["data"]
    assert "access_token" in ref_data
    assert "refresh_token" in ref_data
    assert ref_data["refresh_token"] != refresh_token
    
    # 5. Logout
    new_access = ref_data["access_token"]
    logout_headers = {
        "X-Client-Type": "mobile",
        "Authorization": f"Bearer {new_access}"
    }
    logout_resp = await client.post("/api/v1/auth/logout", headers=logout_headers)
    assert logout_resp.status_code == 200
    
    # 6. Verify /me returns 401 after logout
    me_after_logout = await client.get("/api/v1/auth/me", headers=logout_headers)
    assert me_after_logout.status_code == 401
