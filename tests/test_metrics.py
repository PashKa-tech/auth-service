import pytest
from httpx import AsyncClient
from tests.conftest import TEST_API_KEY

@pytest.mark.asyncio
async def test_metrics_endpoint_and_tracking(client: AsyncClient):
    headers = {"X-Api-Key": TEST_API_KEY}

    # 1. Trigger some requests to generate metrics
    resp_health = await client.get("/health")
    assert resp_health.status_code == 200

    # 2. Get the /metrics endpoint
    resp_metrics = await client.get("/metrics")
    assert resp_metrics.status_code == 200
    metrics_text = resp_metrics.text
    
    # Verify default prometheus and custom request latency metrics are present
    assert "auth_request_duration_seconds" in metrics_text
    
    # 3. Perform a login attempt to verify login metrics tracking
    email = "metrics_user@example.com"
    password = "SuperPassword123!"

    # Register
    await client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": password}
    )

    # Failed login attempt
    await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": "wrongpassword"}
    )

    # Successful login attempt
    await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password}
    )

    # 4. Fetch metrics again and verify auth_login_total is recorded
    resp_metrics2 = await client.get("/metrics")
    assert resp_metrics2.status_code == 200
    metrics_text2 = resp_metrics2.text

    assert "auth_login_total" in metrics_text2
    assert 'status="failed"' in metrics_text2
    assert 'status="success"' in metrics_text2
