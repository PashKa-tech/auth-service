<div align="center">
  <h1>🛡️ Auth Service (Enterprise IAM)</h1>
  <p>
    <strong>A Production-Ready, Secure, and Scalable Identity & Access Management System.</strong><br>
    Built with modern technologies: FastAPI, React, PostgreSQL, and Redis.
  </p>
</div>

<br />

> **Status:** Open Source Release ready.
> **Philosophy:** *Security by default. Beautiful by design.*

## ✨ Features

- **Next-Gen Authentication:** Fully compliant **OAuth2** (Google, GitHub, etc.) and hardware-backed **WebAuthn (Passkeys)** support.
- **Enterprise MFA (Step-up Auth):** Sophisticated Multi-Factor Authentication that intelligently prompts for step-up verification during highly sensitive actions (e.g., account linking, password resets).
- **Bulletproof Security:** Strict CSRF defenses, session fixation protections, explicit token lifecycle management, and hardware attestation enforcement (`require_user_verification=True`).
- **Dynamic Rate Limiting:** Layered Redis-based rate limiting (per-tenant, per-IP, per-user) via declarative dependency injection.
- **Minimalist Aesthetic:** A beautifully crafted, responsive B&W minimalist frontend built with React and Vanilla CSS.
- **Multi-tenant Architecture:** Built from the ground up to support isolation and scalable access paradigms.

## 🏗️ Architecture

The system is decoupled into two primary layers:

### Backend (`/backend`)
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **Database:** PostgreSQL (managed via SQLAlchemy 2.0 & Alembic)
- **Cache & Rate Limiting:** Redis
- **Security Primitives:** Standard-compliant JWT (RS256), opaque refresh tokens (SHA-256 hashed), constant-time cryptographic comparisons, and comprehensive threat-model defenses.

### Frontend (`/frontend`)
- **Framework:** React + Vite (TypeScript)
- **Design:** Custom-built, zero-dependency minimalist UI.
- **Flows:** Intelligent routing handles complex multi-step state machines (e.g., Redirect to OAuth → MFA Challenge → Dashboard).

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ & Node.js 20+ (for local development)

### Quick Start (Docker)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/PashKa-tech/auth-service.git
   cd auth-service
   ```

2. **Configure your environment:**
   ```bash
   cp backend/.env.example backend/.env
   # Add your specific OAuth credentials and keys to backend/.env
   ```

3. **Spin up the stack:**
   ```bash
   docker-compose up --build -d
   ```

4. **Access the application:**
   - Frontend is running at: `http://localhost:3000`
   - Backend API Docs are at: `http://localhost:8000/docs`

## 🔒 Security & Threat Model

This service is engineered to act as a definitive boundary between hostile networks and internal infrastructure. 
- Please read our [THREAT_MODEL.md](./THREAT_MODEL.md) to understand the trust boundaries, token lifecycles, and replay-protection mechanisms.
- Vulnerabilities? Please refer to our [SECURITY.md](./SECURITY.md) for our responsible disclosure policy.

## 🛠️ Local Development

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## 🧪 Testing

We utilize `pytest` for backend coverage, including rigorous property-based fuzzing using `hypothesis` to ensure cryptographic integrity at the absolute boundaries.

```bash
cd backend
PYTHONPATH=. pytest
```

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
