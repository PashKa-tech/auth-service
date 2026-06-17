import pytest
import pyotp
from httpx import AsyncClient
from tests.conftest import TEST_API_KEY, TEST_TENANT_ID

@pytest.mark.asyncio
async def test_2fa_full_flow(client: AsyncClient):
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "2fa_user@example.com"
    password = "SuperPassword123!"

    # 1. Register user
    reg_resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201

    # 2. Login (normal flow - 2FA is disabled)
    login_resp = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["data"].get("requires_2fa") is not True
    cookies = login_resp.cookies
    assert "access_token" in cookies

    # 3. Setup 2FA
    setup_resp = await client.post(
        "/api/v1/auth/2fa/setup",
        headers=headers,
        cookies=cookies
    )
    assert setup_resp.status_code == 200
    setup_data = setup_resp.json()["data"]
    assert "totp_secret" in setup_data
    assert "provisioning_uri" in setup_data
    assert "backup_codes" in setup_data
    assert len(setup_data["backup_codes"]) == 10

    totp_secret = setup_data["totp_secret"]
    backup_codes = setup_data["backup_codes"]

    # 4. Confirm setup with invalid code (should fail)
    confirm_resp = await client.post(
        "/api/v1/auth/2fa/confirm-setup",
        headers=headers,
        cookies=cookies,
        json={"totp_code": "000000"}
    )
    assert confirm_resp.status_code == 400

    # 5. Confirm setup with valid code
    totp = pyotp.TOTP(totp_secret)
    valid_code = totp.now()
    confirm_resp = await client.post(
        "/api/v1/auth/2fa/confirm-setup",
        headers=headers,
        cookies=cookies,
        json={"totp_code": valid_code}
    )
    assert confirm_resp.status_code == 200

    # 6. Login again (should require 2FA)
    login_resp2 = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_resp2.status_code == 200
    login_data = login_resp2.json()["data"]
    assert login_data["requires_2fa"] is True
    assert "mfa_token" in login_data
    mfa_token = login_data["mfa_token"]

    # 7. Verify 2FA with invalid code
    verify_resp = await client.post(
        "/api/v1/auth/2fa/verify",
        headers=headers,
        json={"mfa_token": mfa_token, "totp_code": "000000"}
    )
    assert verify_resp.status_code == 401

    # 8. Verify 2FA with valid code
    valid_code = totp.now()
    verify_resp = await client.post(
        "/api/v1/auth/2fa/verify",
        headers=headers,
        json={"mfa_token": mfa_token, "totp_code": valid_code}
    )
    assert verify_resp.status_code == 200
    assert "access_token" in verify_resp.cookies

@pytest.mark.asyncio
async def test_2fa_backup_codes(client: AsyncClient):
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "2fa_backup@example.com"
    password = "SuperPassword123!"

    # 1. Register & Setup
    await client.post("/api/v1/auth/register", headers=headers, json={"email": email, "password": password})
    
    # Login & Setup 2FA
    login_resp = await client.post("/api/v1/auth/login", headers=headers, json={"email": email, "password": password})
    cookies = login_resp.cookies
    
    setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=headers, cookies=cookies)
    setup_data = setup_resp.json()["data"]
    totp_secret = setup_data["totp_secret"]
    backup_codes = setup_data["backup_codes"]
    
    # Confirm
    totp = pyotp.TOTP(totp_secret)
    await client.post("/api/v1/auth/2fa/confirm-setup", headers=headers, cookies=cookies, json={"totp_code": totp.now()})

    # 2. Login (requires 2FA)
    login_resp2 = await client.post("/api/v1/auth/login", headers=headers, json={"email": email, "password": password})
    mfa_token = login_resp2.json()["data"]["mfa_token"]

    # 3. Verify with backup code
    backup_code = backup_codes[0]
    verify_resp = await client.post(
        "/api/v1/auth/2fa/verify",
        headers=headers,
        json={"mfa_token": mfa_token, "totp_code": backup_code}
    )
    assert verify_resp.status_code == 200
    assert "access_token" in verify_resp.cookies
    
    # 4. Attempt login again, try to REUSE the same backup code (should fail)
    login_resp3 = await client.post("/api/v1/auth/login", headers=headers, json={"email": email, "password": password})
    mfa_token3 = login_resp3.json()["data"]["mfa_token"]
    
    verify_resp3 = await client.post(
        "/api/v1/auth/2fa/verify",
        headers=headers,
        json={"mfa_token": mfa_token3, "totp_code": backup_code}
    )
    assert verify_resp3.status_code == 401

@pytest.mark.asyncio
async def test_2fa_regenerate_and_disable(client: AsyncClient):
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "2fa_manage@example.com"
    password = "SuperPassword123!"

    # Register, login, setup & confirm 2FA
    await client.post("/api/v1/auth/register", headers=headers, json={"email": email, "password": password})
    login_resp = await client.post("/api/v1/auth/login", headers=headers, json={"email": email, "password": password})
    cookies = login_resp.cookies
    
    setup_resp = await client.post("/api/v1/auth/2fa/setup", headers=headers, cookies=cookies)
    setup_data = setup_resp.json()["data"]
    totp_secret = setup_data["totp_secret"]
    backup_codes = setup_data["backup_codes"]
    
    totp = pyotp.TOTP(totp_secret)
    await client.post("/api/v1/auth/2fa/confirm-setup", headers=headers, cookies=cookies, json={"totp_code": totp.now()})

    # 1. Regenerate backup codes
    regen_resp = await client.post("/api/v1/auth/2fa/backup-codes/regenerate", headers=headers, cookies=cookies)
    assert regen_resp.status_code == 200
    new_backup_codes = regen_resp.json()["data"]["backup_codes"]
    assert len(new_backup_codes) == 10
    assert new_backup_codes != backup_codes

    # Verify old backup code does NOT work now
    login_resp2 = await client.post("/api/v1/auth/login", headers=headers, json={"email": email, "password": password})
    mfa_token = login_resp2.json()["data"]["mfa_token"]
    
    verify_resp = await client.post(
        "/api/v1/auth/2fa/verify",
        headers=headers,
        json={"mfa_token": mfa_token, "totp_code": backup_codes[0]}
    )
    assert verify_resp.status_code == 401

    # Verify new backup code works
    verify_resp2 = await client.post(
        "/api/v1/auth/2fa/verify",
        headers=headers,
        json={"mfa_token": mfa_token, "totp_code": new_backup_codes[0]}
    )
    assert verify_resp2.status_code == 200

    # 2. Disable 2FA with invalid credentials (should fail)
    disable_resp = await client.post(
        "/api/v1/auth/2fa/disable",
        headers=headers,
        cookies=cookies,
        json={"password": "wrongpassword"}
    )
    assert disable_resp.status_code == 400

    # Disable 2FA with valid password
    disable_resp2 = await client.post(
        "/api/v1/auth/2fa/disable",
        headers=headers,
        cookies=cookies,
        json={"password": password}
    )
    assert disable_resp2.status_code == 200

    # Verify login no longer prompts for 2FA
    login_resp3 = await client.post("/api/v1/auth/login", headers=headers, json={"email": email, "password": password})
    assert login_resp3.status_code == 200
    assert "access_token" in login_resp3.cookies
