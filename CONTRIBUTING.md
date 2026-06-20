# Contributing to Auth Service

First off, thank you for considering contributing to Auth Service! It's people like you that make open-source a great community.

## Development Setup

We use Docker Compose to make local development as seamless as possible.

### Prerequisites
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/PashKa-tech/auth-service.git
   cd auth-service
   ```

2. Start the infrastructure:
   ```bash
   docker-compose up -d
   ```
   This will spin up PostgreSQL, Redis, Backend (FastAPI), Frontend (React/Vite), Traefik, Prometheus, and Grafana.

3. The services are now available locally:
   - Frontend: `http://localhost` or `http://localhost:8080`
   - Backend API: `http://api.localhost` or `http://localhost:8000`
   - API Docs: `http://api.localhost/docs`
   - Grafana Dashboard: `http://grafana.localhost`

### Submitting Changes
1. Fork the repo and create your branch from `main`.
2. Make sure your code is clean and tested.
3. Run `npm run lint` in the `frontend` folder.
4. Run `pytest` in the `backend` folder.
5. Issue that pull request!

## Code Style
- Python: We follow `PEP8` guidelines.
- TypeScript/React: We use `eslint` and `prettier`. Please ensure your code lints without errors.
