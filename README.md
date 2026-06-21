# 🛡️ OmniAuth / Enterprise Auth Service

[🇺🇸 English Version](#-english-version) | [🇷🇺 Русская Версия](#-русская-версия)

---

## 🇺🇸 English Version

<div align="center">
  <img src="https://via.placeholder.com/150x150?text=AuthService+Logo" alt="Auth Service Logo" width="120" height="120" />

  <h1>OmniAuth Service</h1>
  
  <p>
    <strong>Next-generation, multi-tenant authentication & identity management platform.</strong>
  </p>
  
  <p>
    <a href="https://github.com/PashKa-tech/auth-service/actions"><img src="https://img.shields.io/github/actions/workflow/status/PashKa-tech/auth-service/ci.yml?branch=main&style=for-the-badge" alt="Build Status"></a>
    <a href="https://codecov.io/gh/PashKa-tech/auth-service"><img src="https://img.shields.io/codecov/c/github/PashKa-tech/auth-service?style=for-the-badge" alt="Coverage"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Version"></a>
    <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI"></a>
    <a href="https://reactjs.org/"><img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React"></a>
    <a href="https://www.postgresql.org/"><img src="https://img.shields.io/badge/PostgreSQL-15-336791.svg?style=for-the-badge&logo=postgresql" alt="PostgreSQL"></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License: MIT"></a>
  </p>
  
  <h3>
    <a href="#-features">Features</a>
    <span> | </span>
    <a href="ARCHITECTURE.md">Architecture</a>
    <span> | </span>
    <a href="#-quickstart">Quickstart</a>
    <span> | </span>
    <a href="#-documentation">Documentation</a>
  </h3>
</div>

<br/>

OmniAuth is an open-source identity and access management (IAM) solution designed to rival enterprise platforms like Auth0. Built from the ground up for performance, security, and scalability, it features a blazingly fast FastAPI backend, a sleek React frontend, and a highly scalable PostgreSQL/Redis foundation adhering to Clean Architecture principles.

### ✨ Features

- **Robust Core Stack**: Built on top of **FastAPI**, **React**, **PostgreSQL**, and **Redis** for unparalleled speed and reliability.
- **Multi-tenant Architecture**: Natively support B2B SaaS use-cases with isolated data stores, custom domains, and custom branding per tenant.
- **Next-Gen Authentication**: Support for **WebAuthn (Passkeys)** out of the box, offering secure, passwordless login experiences.
- **Federated Login (OAuth 2.0)**: Connect with your users anywhere. Pre-configured integrations with **7 major providers** (Google, GitHub, Apple, Microsoft, LinkedIn, Facebook, and Twitter).
- **Advanced Security**:
  - Two-Factor Authentication (2FA/MFA) via TOTP and SMS.
  - Password hashing with **Argon2**, mathematically protected against GPU brute-forcing.
  - Granular Role-Based Access Control (RBAC) and Attribute-Based Access Control (ABAC).
  - Built-in Bot Protection with **Google reCAPTCHA v3**, **Custom Captcha** fallback, and **SlowAPI** for rate limiting.
- **Developer First**: Comprehensive Admin Dashboard, exhaustive Audit Logs, and fully typed REST APIs.
- **Premium Interface**: Glassmorphism design, Framer Motion animations, and a global Toast notification system.

### 🚀 Quickstart

#### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.12+ (for local backend development)

#### Up and Running in 3 Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/PashKa-tech/auth-service.git
   cd auth-service
   ```

2. **Configure your environment**
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.local frontend/.env
   # Edit .env to add your specific configuration (Database, Redis, SMTP, OAuth keys)
   ```

3. **Start the platform & Migrate**
   ```bash
   make up
   make migrate
   # OR use docker-compose:
   # docker-compose up -d --build
   # docker-compose exec backend alembic upgrade head
   ```

Your Auth Service is now running via Traefik (or Nginx)! 
- **Frontend Dashboard**: `http://localhost` or `http://localhost:8080`
- **Backend API Docs**: `http://api.localhost` or `http://localhost:8000/docs`
- **Grafana Metrics**: `http://grafana.localhost` (admin/admin)

### 📖 Documentation

For an in-depth look at our design decisions and system components, please read our [Architecture Document](ARCHITECTURE.md).

- **Deployment Guide**: Learn how to deploy to AWS, GCP, or Azure via Kubernetes.
- **API Reference**: Comprehensive Swagger and ReDoc generated documentation.

### 🤝 Contributing

We welcome contributions from the community! Please see our [Contributing Guidelines](CONTRIBUTING.md) to get started.

### 🛡️ License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 🇷🇺 Русская Версия

<div align="center">
  <img src="https://via.placeholder.com/150x150?text=AuthService+Logo" alt="Auth Service Logo" width="120" height="120" />

  <h1>OmniAuth Service (Enterprise Auth Service)</h1>
  
  <p>
    <strong>Платформа следующего поколения для аутентификации и управления доступом с поддержкой мультитенантности.</strong>
  </p>
  
  <p>
    <a href="https://github.com/PashKa-tech/auth-service/actions"><img src="https://img.shields.io/github/actions/workflow/status/PashKa-tech/auth-service/ci.yml?branch=main&style=for-the-badge" alt="Build Status"></a>
    <a href="https://codecov.io/gh/PashKa-tech/auth-service"><img src="https://img.shields.io/codecov/c/github/PashKa-tech/auth-service?style=for-the-badge" alt="Coverage"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Version"></a>
    <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI"></a>
    <a href="https://reactjs.org/"><img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React"></a>
    <a href="https://www.postgresql.org/"><img src="https://img.shields.io/badge/PostgreSQL-15-336791.svg?style=for-the-badge&logo=postgresql" alt="PostgreSQL"></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License: MIT"></a>
  </p>
  
  <h3>
    <a href="#-ключевые-возможности">Возможности</a>
    <span> | </span>
    <a href="ARCHITECTURE.md">Архитектура</a>
    <span> | </span>
    <a href="#-быстрый-старт">Быстрый старт</a>
    <span> | </span>
    <a href="#-документация">Документация</a>
  </h3>
</div>

<br/>

**Enterprise Auth Service (OmniAuth)** — это современная, высоконагруженная и полностью защищенная система аутентификации и авторизации (IAM), построенная на принципах Чистой Архитектуры, являющаяся open-source альтернативой решениям вроде Auth0. Проект предоставляет готовый Identity Provider (IdP) с поддержкой самых современных стандартов безопасности.

### ✨ Ключевые возможности

- **Мощный технологический стек**: Построено на базе **FastAPI**, **React**, **PostgreSQL** и **Redis** для непревзойденной скорости и надежности.
- **B2B Multi-Tenancy (Мультитенантность)**: Нативная поддержка SaaS с изолированными хранилищами данных, кастомными доменами и уникальным брендингом для каждого арендатора (тенанта).
- **Аутентификация следующего поколения**: Поддержка беспарольного входа через **WebAuthn (Passkeys)** "из коробки" (FaceID, TouchID, Windows Hello, YubiKey).
- **OAuth 2.0 (Федеративный вход)**: Готовые интеграции с **7 популярными провайдерами** (Google, GitHub, Apple, Microsoft, LinkedIn, Facebook, Twitter и Discord).
- **Продвинутая безопасность**:
  - Двухфакторная аутентификация (2FA/MFA) через TOTP и SMS.
  - Пароли математически защищены современным алгоритмом **Argon2** (с защитой от брутфорса на GPU).
  - Управление доступом на основе ролей (RBAC) и атрибутов (ABAC).
  - Встроенная защита от ботов и перебора паролей (Rate Limiting) с использованием **SlowAPI**, **Google reCAPTCHA v3** и резервной Captcha.
- **С фокусом на разработчиков**: Полноценная панель администратора, детальные логи аудита (Audit Logs) и полностью типизированный REST API.
- **Premium Интерфейс (UI/UX)**: Glassmorphism дизайн, плавные анимации Framer Motion и глобальная система Toast уведомлений.

### 🚀 Быстрый старт

#### Требования
- [Docker](https://docs.docker.com/get-docker/) и Docker Compose
- Node.js 18+ (для локальной разработки фронтенда)
- Python 3.12+ (для локальной разработки бэкенда)

#### Запуск за 3 шага

1. **Клонирование репозитория**
   ```bash
   git clone https://github.com/PashKa-tech/auth-service.git
   cd auth-service
   ```

2. **Настройка окружения**
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.local frontend/.env
   # Отредактируйте .env для добавления вашей конфигурации (БД, Redis, SMTP, ключи OAuth)
   ```

3. **Запуск платформы и миграции**
   ```bash
   make up
   make migrate
   # ИЛИ используйте docker-compose:
   # docker-compose up -d --build
   # docker-compose exec backend alembic upgrade head
   ```

Ваш Auth Service теперь запущен через Traefik (или Nginx)! 
- **Frontend Dashboard**: `http://localhost` или `http://localhost:8080`
- **Backend API Docs**: `http://api.localhost` или `http://localhost:8000/docs` (Интерактивный Swagger UI)
- **Мониторинг Grafana**: `http://grafana.localhost` (admin/admin)

### 📖 Документация

Для детального ознакомления с нашими архитектурными решениями, пожалуйста, прочитайте наш [Документ по Архитектуре](ARCHITECTURE.md).

- **Гайд по развертыванию**: Узнайте, как развернуть систему в AWS, GCP или Azure с помощью Kubernetes (в процессе подготовки).
- **API Документация**: Автоматически сгенерированная и всегда актуальная документация Swagger и ReDoc.

### 🤝 Участие в разработке

Мы приветствуем вклад сообщества в проект! Пожалуйста, ознакомьтесь с нашими [Правилами участия (Contributing)](CONTRIBUTING.md) для начала работы.

### 🛡️ Лицензия

Распространяется под лицензией MIT. Дополнительную информацию см. в файле `LICENSE`.
