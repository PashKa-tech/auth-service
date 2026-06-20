import pytest
from httpx import AsyncClient

HEADERS = {"X-API-Key": "test_developer_key"}

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
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
async def test_register_duplicate(client: AsyncClient):
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
    assert data["error"]["code"] == "HTTP_ERROR"

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "password123"},
        headers=HEADERS
    )
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
async def test_login_invalid_credentials(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpassword"},
        headers=HEADERS
    )
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "HTTP_ERROR"
