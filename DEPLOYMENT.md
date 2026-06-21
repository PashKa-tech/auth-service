# Deployment Guide

This guide describes how to deploy the OmniAuth Service (Enterprise Auth Service) for production environments.

## Architecture Overview

The system consists of:
1. **FastAPI Backend**: Handles core logic, Auth workflows, and database interactions.
2. **React Frontend**: The administrative dashboard and user-facing login/registration interfaces.
3. **PostgreSQL 15+**: Primary relational datastore.
4. **Redis 7+**: Used for caching, rate limiting, and temporary session data.
5. **Reverse Proxy (Traefik/Nginx)**: Handles SSL termination and request routing.

## Prerequisites

- Docker and Docker Compose
- A registered domain name
- An SMTP server for email delivery
- OAuth Client IDs and Secrets (Google, GitHub, etc.)

## Quick Deployment (Docker Compose)

The easiest way to deploy for small-to-medium scale is using Docker Compose.

1. **Clone the repository on your server:**
   ```bash
   git clone https://github.com/PashKa-tech/auth-service.git
   cd auth-service
   ```

2. **Configure Environment Variables:**
   Copy the example environment files and fill them in with production secrets.
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.local frontend/.env
   ```
   **Critical Settings to update:**
   - `SECRET_KEY` (Generate a strong random string)
   - `DATABASE_URL` (Use a strong password)
   - `DOMAIN` and `FRONTEND_URL`
   - `SMTP_*` variables for email sending

3. **Build and Run:**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

4. **Run Database Migrations:**
   ```bash
   docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
   ```

## Production Considerations

### 1. Security
- Ensure your reverse proxy (Traefik or Nginx) enforces HTTPS using Let's Encrypt or your custom certificates.
- Do not expose the PostgreSQL or Redis ports to the public internet. Ensure they only bind to Docker's internal network.

### 2. High Availability (Kubernetes)
For large-scale deployments, we recommend using Kubernetes (K8s). Helm charts are currently being developed.
Ensure that:
- The FastAPI backend pods can scale horizontally behind a load balancer.
- Redis is deployed in Sentinel or Cluster mode.
- PostgreSQL uses a managed service (e.g., AWS RDS, GCP Cloud SQL) or Patroni for high availability.

### 3. Monitoring
OmniAuth integrates with Grafana/Prometheus out of the box (if configured). 
Ensure you secure the `/metrics` endpoint and monitor:
- HTTP Response codes (4xx/5xx spikes)
- Database connection pools
- Redis cache hit rates and memory usage

## Backup and Recovery
- Run daily automated backups of your PostgreSQL database (`pg_dump`).
- Redis data is mostly ephemeral (sessions, rate limits), but if using it as a primary store for long-lived captchas or pending webhook deliveries, configure RDB snapshots.
