import pytest
from httpx import AsyncClient

HEADERS = {"X-API-Key": "test_developer_key"}

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, verify_user):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123"},
        headers=HEADERS
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient, verify_user):
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={"email": "duplicate@example.com", "password": "password123"},
        headers=HEADERS
    )
    # Second registration
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "duplicate@example.com", "password": "password123"},
        headers=HEADERS
    )
    assert response.status_code == 409
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CONFLICT"

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, verify_user):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "password123"},
        headers=HEADERS
    )
    await verify_user("login@example.com")
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
        headers=HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, verify_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpassword"},
        headers=HEADERS
    )
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "HTTP_ERROR"
