import pytest
import uuid
from httpx import AsyncClient
from tests.conftest import TEST_API_KEY, TEST_TENANT_ID
from src.core.redis import init_redis
from src.models.user import User
from sqlalchemy import select

@pytest.fixture(autouse=True)
async def clean_redis():
    redis_client = await init_redis()
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()

@pytest.mark.asyncio
async def test_email_verification_flow(client: AsyncClient, db_session):
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "verify_test@example.com"
    password = "SuperPassword123!"

    # 1. Register User
    reg_resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["data"]["id"]

    # Verify initially not verified
    me_check = await db_session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user_obj = me_check.scalar_one()
    assert user_obj.is_verified is False

    # 2. Login to get cookies/token
    login_resp = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    cookies = login_resp.cookies

    # 3. Request email verification
    req_verify_resp = await client.post(
        "/api/v1/auth/request-verification",
        headers=headers,
        cookies=cookies
    )
    assert req_verify_resp.status_code == 200
    assert req_verify_resp.json()["success"] is True

    # 4. Grab the verification token from Redis
    redis_client = await init_redis()
    keys = await redis_client.keys("email_verify:*")
    assert len(keys) == 1
    verify_key = keys[0]
    token = verify_key.split(":")[1]

    # Verify that the value stored in Redis is the user_id
    val = await redis_client.get(verify_key)
    assert val == user_id

    # 5. Call GET /verify-email?token=<token>&tenant_id=<tenant_id>
    verify_resp = await client.get(
        f"/api/v1/auth/verify-email?token={token}&tenant_id={TEST_TENANT_ID}"
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["success"] is True

    # Verify user is verified in DB
    await db_session.refresh(user_obj)
    assert user_obj.is_verified is True

    # Verify token is deleted from Redis
    assert await redis_client.get(verify_key) is None


@pytest.mark.asyncio
async def test_password_reset_flow(client: AsyncClient, db_session):
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "reset_test@example.com"
    password = "OldPassword123!"
    new_password = "NewPassword123!"

    # 1. Register User
    reg_resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["data"]["id"]

    # 2. Request Password Reset
    forgot_resp = await client.post(
        "/api/v1/auth/forgot-password",
        headers=headers,
        json={"email": email}
    )
    assert forgot_resp.status_code == 200
    assert forgot_resp.json()["success"] is True

    # 3. Grab reset token from Redis
    redis_client = await init_redis()
    keys = await redis_client.keys("password_reset:*")
    assert len(keys) == 1
    reset_key = keys[0]
    token = reset_key.split(":")[1]

    # 4. Perform Password Reset using token
    # This checks if resolve_tenant resolves the tenant context from the POST body token
    reset_resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": new_password}
    )
    assert reset_resp.status_code == 200
    assert reset_resp.json()["success"] is True

    # Verify token is deleted from Redis
    assert await redis_client.get(reset_key) is None

    # 5. Try logging in with old password (should fail)
    login_old = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_old.status_code == 401

    # 6. Try logging in with new password (should succeed)
    login_new = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": new_password}
    )
    assert login_new.status_code == 200
    assert login_new.json()["success"] is True


@pytest.mark.asyncio
async def test_2fa_email_notifications(client: AsyncClient, db_session, monkeypatch):
    from src.services.email import EmailService
    
    sent_emails = []
    async def mock_send_email(self, to_email: str, subject: str, body: str):
        sent_emails.append((to_email, subject, body))
    monkeypatch.setattr(EmailService, "send_email", mock_send_email)
    
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "mfa_notify_test@example.com"
    password = "SuperPassword123!"
    
    # 1. Register User
    reg_resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201
    
    # 2. Login to get cookies
    login_resp = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    cookies = login_resp.cookies
    
    # 3. Setup 2FA
    setup_resp = await client.post(
        "/api/v1/auth/2fa/setup",
        headers=headers,
        cookies=cookies
    )
    assert setup_resp.status_code == 200
    totp_secret = setup_resp.json()["data"]["totp_secret"]
    
    # 4. Confirm 2FA (should trigger confirm email)
    import pyotp
    totp = pyotp.TOTP(totp_secret)
    totp_code = totp.now()
    
    confirm_resp = await client.post(
        "/api/v1/auth/2fa/confirm-setup",
        headers=headers,
        cookies=cookies,
        json={"totp_code": totp_code}
    )
    assert confirm_resp.status_code == 200
    
    # Assert 2FA Enabled email was sent
    assert len(sent_emails) == 1
    assert sent_emails[0][0] == email
    assert "включена" in sent_emails[0][1]
    
    # 5. Regenerate backup codes (should trigger regenerate email)
    regen_resp = await client.post(
        "/api/v1/auth/2fa/backup-codes/regenerate",
        headers=headers,
        cookies=cookies
    )
    assert regen_resp.status_code == 200
    
    # Assert backup codes regenerated email sent
    assert len(sent_emails) == 2
    assert sent_emails[1][0] == email
    assert "резервные коды" in sent_emails[1][1].lower()
    
    # 6. Disable 2FA (should trigger disable email)
    disable_resp = await client.post(
        "/api/v1/auth/2fa/disable",
        headers=headers,
        cookies=cookies,
        json={"totp_code": totp_code}
    )
    assert disable_resp.status_code == 200
    
    # Assert 2FA Disabled email sent
    assert len(sent_emails) == 3
    assert sent_emails[2][0] == email
    assert "отключена" in sent_emails[2][1]


@pytest.mark.asyncio
async def test_suspicious_login_email_notification(client: AsyncClient, db_session, monkeypatch):
    from src.services.email import EmailService
    
    sent_emails = []
    async def mock_send_email(self, to_email: str, subject: str, body: str):
        sent_emails.append((to_email, subject, body))
    monkeypatch.setattr(EmailService, "send_email", mock_send_email)
    
    # Mock get_country_from_ip to return different countries
    from src.services import auth
    countries = ["US", "US", "DE"]  # First two sessions US, third one DE (anomaly)
    country_index = 0
    
    def mock_get_country_from_ip(ip: str) -> str:
        nonlocal country_index
        c = countries[country_index % len(countries)]
        country_index += 1
        return c
    
    monkeypatch.setattr(auth, "get_country_from_ip", mock_get_country_from_ip)
    
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "anomaly_notify_test@example.com"
    password = "SuperPassword123!"
    
    # 1. Register
    reg_resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201
    
    # 2. Login 1 (from IP 1.1.1.1 -> US)
    login1 = await client.post(
        "/api/v1/auth/login",
        headers={**headers, "X-Forwarded-For": "1.1.1.1"},
        json={"email": email, "password": password}
    )
    assert login1.status_code == 200
    
    # 3. Login 2 (from IP 2.2.2.2 -> US)
    login2 = await client.post(
        "/api/v1/auth/login",
        headers={**headers, "X-Forwarded-For": "2.2.2.2"},
        json={"email": email, "password": password}
    )
    assert login2.status_code == 200
    
    # 4. Login 3 (from IP 3.3.3.3 -> DE -> Anomaly alert!)
    login3 = await client.post(
        "/api/v1/auth/login",
        headers={**headers, "X-Forwarded-For": "3.3.3.3"},
        json={"email": email, "password": password}
    )
    assert login3.status_code == 200
    
    # Assert anomaly notification email was sent
    assert len(sent_emails) == 1
    assert sent_emails[0][0] == email
    assert "подозрительный вход" in sent_emails[0][1]
    assert "DE" in sent_emails[0][2]

