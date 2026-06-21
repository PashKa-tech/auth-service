import pytest
from httpx import AsyncClient
from tests.conftest import TEST_API_KEY

@pytest.mark.asyncio
async def test_webauthn_flows(client: AsyncClient, verify_user):
    """Test generating WebAuthn registration options."""
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "passkey_user@example.com"
    password = "SuperPassword123!"
    
    # 1. Register User
    await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    
    # 2. Login User
    login_resp = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    cookies = login_resp.cookies

    # 3. Test webauthn/register/begin
    reg_begin_resp = await client.post(
        "/api/v1/auth/webauthn/register/begin",
        headers=headers,
        cookies=cookies
    )
    assert reg_begin_resp.status_code == 200
    data = reg_begin_resp.json()
    assert data["success"] is True
    assert "challenge" in data["data"]
    assert "user" in data["data"]

    # 4. Test webauthn/register/complete with invalid data
    reg_complete_resp = await client.post(
        "/api/v1/auth/webauthn/register/complete",
        headers=headers,
        cookies=cookies,
        json={
            "response": {"id": "invalid", "rawId": "invalid", "type": "public-key", "response": {}},
            "name": "Test Key"
        }
    )
    assert reg_complete_resp.status_code == 400

    # 5. Test webauthn/login/begin for invalid user
    login_begin_resp1 = await client.post(
        "/api/v1/auth/webauthn/login/begin",
        headers=headers,
        json={"email": "nobody@example.com"}
    )
    print(login_begin_resp1.json())
    assert login_begin_resp1.status_code == 400

    # 6. Test webauthn/login/begin for user without keys
    login_begin_resp2 = await client.post(
        "/api/v1/auth/webauthn/login/begin",
        headers=headers,
        json={"email": email}
    )
    print(login_begin_resp2.json())
    assert login_begin_resp2.status_code == 400
