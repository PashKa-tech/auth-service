import pytest
import uuid
from httpx import AsyncClient
from tests.conftest import TEST_API_KEY
from src.models.user import User
from sqlalchemy import select

@pytest.mark.asyncio
async def test_rbac_admin_only_flow(client: AsyncClient, db_session, verify_user):
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "rbac_test@example.com"
    password = "SuperPassword123!"

    # 1. Register User (Default role is "user")
    reg_resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["data"]["id"]
    await verify_user(email)

    # 2. Login to get browser cookies
    login_resp = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_resp.status_code == 200
    cookies = login_resp.cookies

    # 3. Access GET /admin-only (should be blocked with 403 Forbidden)
    admin_blocked = await client.get("/api/v1/auth/admin-only", cookies=cookies)
    assert admin_blocked.status_code == 403
    assert "insufficient permissions" in admin_blocked.json()["error"]["message"].lower()

    # 4. Manually update the user's role to "admin" in the database
    result = await db_session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user_obj = result.scalar_one()
    user_obj.role = "admin"
    await db_session.commit()

    # 5. Log in again to obtain a token with the new "admin" role
    login_admin = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert login_admin.status_code == 200
    cookies_admin = login_admin.cookies

    # 6. Access GET /admin-only (should succeed with 200 OK)
    admin_success = await client.get("/api/v1/auth/admin-only", cookies=cookies_admin)
    assert admin_success.status_code == 200
    assert admin_success.json()["success"] is True
    assert admin_success.json()["data"]["message"] == "Welcome, Admin!"
