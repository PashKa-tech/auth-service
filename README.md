<div align="center">
  <img src="https://raw.githubusercontent.com/github/explore/80688e429a7d4ef2fca1e82350fe8e3517d3494d/topics/security/security.png" alt="Auth Service Logo" width="120" />

  <h1>🛡️ Auth Service</h1>
  <p><i>Next-Generation Enterprise Authentication & Authorization Platform</i></p>

  <p>
    <a href="https://github.com/PashKa-tech/auth-service/actions"><img src="https://img.shields.io/badge/build-passing-brightgreen.svg?style=for-the-badge" alt="Build Status"></a>
    <a href="https://github.com/PashKa-tech/auth-service/releases"><img src="https://img.shields.io/badge/version-v1.0.0-blue.svg?style=for-the-badge" alt="Version"></a>
    <a href="https://github.com/PashKa-tech/auth-service/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge" alt="License"></a>
    <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.103.0-009688.svg?style=for-the-badge&logo=fastapi" alt="FastAPI"></a>
    <a href="https://react.dev/"><img src="https://img.shields.io/badge/React-18.0-61DAFB.svg?style=for-the-badge&logo=react" alt="React"></a>
  </p>
</div>

<hr />

## ✨ Features

- **🔑 Passkeys (WebAuthn)**: Passwordless, phishing-resistant authentication using biometrics.
- **🌐 OAuth 2.0 & OIDC**: Seamless SSO integration with leading identity providers (Google, GitHub, Microsoft).
- **🛡️ 2FA / MFA**: Multi-factor authentication supporting TOTP and SMS.
- **🎫 JWT Management**: Secure stateless sessions with robust token rotation and revocation.
- **⚡ High Performance**: Built with asynchronous Python (FastAPI) handling thousands of reqs/sec.
- **🎨 Modern UI**: A blazing-fast, responsive dashboard built with React and Vite.

## 🛠️ Tech Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis (Rate Limiting, Session Storage)

### Frontend
- **Framework**: [React](https://react.dev/)
- **Build Tool**: [Vite](https://vitejs.dev/)
- **Styling**: Tailwind CSS / Vanilla CSS

### DevOps
- **Containerization**: Docker & Docker Compose
- **CI/CD**: GitHub Actions

## 🏗️ Architecture

```mermaid
graph TD
    Client[Client App / Browser] -->|HTTPS| Gateway[API Gateway / Load Balancer]
    
    subgraph "Frontend Layer"
        ReactApp[React SPA Vite]
    end
    
    Gateway -->|Static Assets| ReactApp
    Gateway -->|API Requests| AuthAPI[FastAPI Auth Service]
    
    subgraph "Core Authentication Layer"
        AuthAPI -->|OAuth| ExternalIdP[External Identity Providers]
        AuthAPI -->|Passkeys| WebAuthn[WebAuthn Module]
        AuthAPI -->|2FA| MFAModule[TOTP / SMS Service]
        AuthAPI -->|JWT| TokenService[Token Issuance & Validation]
    end
    
    subgraph "Data Layer"
        AuthAPI -->|Read/Write| Postgres[(PostgreSQL DB)]
        AuthAPI -->|Session/Cache| Redis[(Redis Cache)]
    end
```

## 🚀 Setup Instructions

### Prerequisites
- [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/)
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/PashKa-tech/auth-service.git
   cd auth-service
   ```

2. **Environment Configuration**
   Copy the example environment file and configure your secrets:
   ```bash
   cp .env.example .env
   ```

3. **Start the Platform**
   Deploy the entire stack (Frontend, Backend, Database, Cache) with a single command:
   ```bash
   docker-compose up -d --build
   ```

4. **Access the Services**
   - 🌐 **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
   - 📖 **API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

## 📖 Documentation

For detailed guides, please refer to our [Wiki](https://github.com/PashKa-tech/auth-service/wiki).

## 🤝 Contributing

We welcome contributions! Please review our [Contribution Guidelines](CONTRIBUTING.md) before submitting a pull request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
