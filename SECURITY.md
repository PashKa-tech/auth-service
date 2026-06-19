# Security Policy

## Supported Versions

Currently, only the `main` branch (latest release) receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| older   | :x:                |

## Reporting a Vulnerability

Security is a core priority for `auth-service`. If you discover a vulnerability, please report it immediately.

### How to Report
- Do **NOT** open a public issue for a security vulnerability.
- Please email your findings directly to the security team or the repository maintainer.
- Include a detailed description of the vulnerability, steps to reproduce, and potential impact.

### Response Timeline
- We will acknowledge receipt of your vulnerability report within 48 hours.
- We will provide a status update every 7 days until the issue is resolved.
- Once a fix is deployed, we will coordinate public disclosure (if applicable).

## Best Practices for Deploying
- Always enforce **TLS/HTTPS** in production. The backend issues secure cookies which will be rejected over plain HTTP.
- Ensure the **Redis** and **PostgreSQL** ports are inaccessible from the public internet.
- Rotate the private/public JWT keys and database credentials periodically.
