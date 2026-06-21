import pytest
from httpx import AsyncClient
from tests.conftest import TEST_API_KEY
from src.models.audit import AuditLog
from sqlalchemy import select

@pytest.mark.asyncio
async def test_geoip_anomaly_detection_flow(client: AsyncClient, db_session, verify_user):
    headers = {"X-Api-Key": TEST_API_KEY}
    email = "anomaly_user@example.com"
    password = "SuperPassword123!"

    # 1. Register User
    reg_resp = await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201
    await verify_user(email)

    # 2. Login from Australia (1.1.1.1)
    login1 = await client.post(
        "/api/v1/auth/login",
        headers={**headers, "X-Forwarded-For": "1.1.1.1"},
        json={"email": email, "password": password}
    )
    assert login1.status_code == 200

    # 3. Login again from Australia (1.1.1.1)
    login2 = await client.post(
        "/api/v1/auth/login",
        headers={**headers, "X-Forwarded-For": "1.1.1.1"},
        json={"email": email, "password": password}
    )
    assert login2.status_code == 200

    # Verify no suspicious_login_location audit log is written yet
    res = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "suspicious_login_location")
    )
    assert res.scalar_one_or_none() is None

    # 4. Login from USA (8.8.8.8) -> Should trigger anomaly alert
    login3 = await client.post(
        "/api/v1/auth/login",
        headers={**headers, "X-Forwarded-For": "8.8.8.8"},
        json={"email": email, "password": password}
    )
    assert login3.status_code == 200

    # 5. Verify suspicious_login_location audit log was successfully written
    res2 = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "suspicious_login_location")
    )
    audit = res2.scalar_one_or_none()
    assert audit is not None
    assert audit.ip_address == "8.8.8.8"
    
    metadata = audit.metadata_json
    assert metadata["current_country"] == "United States"
    assert "Australia" in metadata["past_countries"]
