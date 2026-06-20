# Auth Service Backend

Welcome to the **Auth Service** backend – a modern, highly scalable, Auth0-like Identity Provider (IdP) built with FastAPI, PostgreSQL, and Redis.

## Features

- **Enterprise Authentication**
  - Registration & Login with email/password
  - Account Lockout on brute-force attempts
  - Argon2id password hashing
  - HaveIBeenPwned password checks
- **Multi-Factor Authentication (MFA)**
  - TOTP (Authenticator Apps)
  - WebAuthn / Passkeys
  - Single-use Backup Codes
- **OAuth 2.0 & Social SSO**
  - Native login with Google, GitHub, Twitter, Discord, Apple, Facebook, Amazon
- **SAML & Enterprise Connections**
  - Support for multiple IdPs mapping to specific domains
- **Multi-Tenancy & RBAC**
  - Data isolated by Tenant IDs
  - Role-Based Access Control (Roles and Permissions)
  - Admin/Tenant scopes
- **Security & Anomaly Detection**
  - Impossible Travel (GeoIP velocity checks)
  - Suspicious Login Alerts
- **Extensibility**
  - Pre-Login Webhooks with custom JWT claims injection
  - OIDC / JWKS (`/.well-known/jwks.json` discovery)
- **Developer API**
  - M2M OAuth Applications and Client Credentials
  - Extensible RESTful API powered by OpenAPI / Swagger

## Tech Stack

- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL 15+ with asyncpg
- **ORM**: SQLAlchemy 2.0 & Alembic (Migrations)
- **Caching & Rate Limiting**: Redis
- **Containerization**: Docker & Docker Compose
- **Testing**: PyTest with HTTPX & Asyncio

## Getting Started

### 1. Requirements

- Python 3.10+
- Docker & Docker Compose (for the database and Redis)

### 2. Environment Variables

Copy the `.env.example` to `.env` or `.env.dev`:
```bash
cp .env.example .env.dev
```
Fill out any necessary SMTP, OAuth, or Captcha tokens. Defaults are mostly ready for local dev.

### 3. Spin up infrastructure

```bash
docker-compose up -d db redis
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run Database Migrations

Apply the Alembic migrations to setup the schemas:
```bash
alembic upgrade head
```

### 6. Start the Server

```bash
python -m uvicorn src.main:app --reload --port 8000
```
Server runs at `http://localhost:8000`.

## API Documentation

Interactive API documentation is automatically generated. Once running, visit:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Testing

To run the test suite, ensure the virtual environment is active and run:
```bash
PYTHONPATH=. pytest
```
_Note: `pytest` automatically uses a temporary SQLite in-memory database and FakerRedis so it does not interfere with the actual PostgreSQL or Redis instances._

## Architecture

- `src/api`: Endpoint controllers (routers).
- `src/core`: Configuration, Security, JWT issuance, Rate Limiters, Anomalies.
- `src/models`: SQLAlchemy declarative models.
- `src/schemas`: Pydantic models for request/response validation.
- `src/services`: Core business logic (Auth, Email, Webhooks, OAuth, etc).
- `tests/`: Comprehensive PyTest suite covering full end-to-end flows.
