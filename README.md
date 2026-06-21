<div align="center">
  <img src="https://via.placeholder.com/150x150?text=AuthService+Logo" alt="Auth Service Logo" width="120" height="120" />

  <h1>OmniAuth Service</h1>
  
  <p>
    <strong>Next-generation, multi-tenant authentication & identity management platform.</strong>
  </p>
  
  <p>
    <a href="https://github.com/PashKa-tech/auth-service/actions"><img src="https://img.shields.io/github/actions/workflow/status/PashKa-tech/auth-service/ci.yml?branch=main&style=for-the-badge" alt="Build Status"></a>
    <a href="https://codecov.io/gh/PashKa-tech/auth-service"><img src="https://img.shields.io/codecov/c/github/PashKa-tech/auth-service?style=for-the-badge" alt="Coverage"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Version"></a>
    <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI"></a>
    <a href="https://reactjs.org/"><img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React"></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License: MIT"></a>
  </p>
  
  <h3>
    <a href="#features">Features</a>
    <span> | </span>
    <a href="ARCHITECTURE.md">Architecture</a>
    <span> | </span>
    <a href="#quickstart">Quickstart</a>
    <span> | </span>
    <a href="#documentation">Documentation</a>
  </h3>
</div>

<br/>

OmniAuth is an open-source identity and access management (IAM) solution designed to rival enterprise platforms like Auth0. Built from the ground up for performance, security, and scalability, it features a blazingly fast FastAPI backend, a sleek React frontend, and a highly scalable PostgreSQL/Redis foundation.

## ✨ Features

- **Robust Core Stack**: Built on top of **FastAPI**, **React**, **PostgreSQL**, and **Redis** for unparalleled speed and reliability.
- **Multi-tenant Architecture**: Natively support B2B SaaS use-cases with isolated data stores, custom domains, and custom branding per tenant.
- **Next-Gen Authentication**: Support for **WebAuthn (Passkeys)** out of the box, offering secure, passwordless login experiences.
- **Federated Login (OAuth 2.0)**: Connect with your users anywhere. Pre-configured integrations with **7 major providers** (Google, GitHub, Apple, Microsoft, LinkedIn, Facebook, and Twitter).
- **Advanced Security**:
  - Two-Factor Authentication (2FA) via TOTP and SMS.
  - Granular Role-Based Access Control (RBAC) and Attribute-Based Access Control (ABAC).
  - Built-in Bot Protection with **Google reCAPTCHA v3** and **Custom Captcha** fallback.
- **Developer First**: Comprehensive Admin Dashboard, exhaustive Audit Logs, and fully typed REST APIs.

---

## 🚀 Quickstart

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Up and Running in 3 Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/PashKa-tech/auth-service.git
   cd auth-service
   ```

2. **Configure your environment**
   ```bash
   cp .env.example .env
   # Edit .env to add your specific configuration (Database, Redis, OAuth keys)
   ```

3. **Start the platform**
   ```bash
   docker-compose up -d
   ```

Your Auth Service is now running via Traefik! 
- **Frontend Dashboard**: `http://localhost` or `http://localhost:8080`
- **Backend API**: `http://api.localhost` or `http://localhost:8000/docs`
- **Grafana Metrics**: `http://grafana.localhost` (admin/admin)

---

## 📖 Documentation

For an in-depth look at our design decisions and system components, please read our [Architecture Document](ARCHITECTURE.md).

- **Deployment Guide**: Learn how to deploy to AWS, GCP, or Azure via Kubernetes.
- **API Reference**: Comprehensive Swagger and ReDoc generated documentation.

## 🤝 Contributing

We welcome contributions from the community! Please see our [Contributing Guidelines](CONTRIBUTING.md) to get started.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🛡️ License

Distributed under the MIT License. See `LICENSE` for more information.
