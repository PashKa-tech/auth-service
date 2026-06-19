# Threat Model & Security Architecture

## 1. Introduction
This document defines the security boundaries, assumed threats, and defensive mechanisms built into the `auth-service` Identity and Access Management (IAM) product. 

## 2. Attacker Model & Trust Boundaries

### 2.1 Untrusted Boundaries
- **Client Devices (Browsers, Mobile Apps)**: Assumed to be potentially compromised, susceptible to malware, or running in hostile environments.
- **Network Layer (Internet)**: Assumed to be actively monitored, intercepted, or manipulated (MitM).
- **Third-party OAuth Providers**: Assumed to be functioning correctly but not inherently trusted with internal system privileges.

### 2.2 Trusted Boundaries
- **Backend Application Server (FastAPI)**: Trusted to execute code securely. Protected by reverse proxy (Nginx/Traefik).
- **Internal Network / Subnets**: Communication between API, Redis, and PostgreSQL must be isolated from the public internet.
- **Database (PostgreSQL) & Cache (Redis)**: Trusted data stores.

### 2.3 Threat Actors
- **External Unauthenticated Actors**: Attempting brute-force attacks, credential stuffing, enumeration, and OAuth flow manipulation (CSRF/Session Fixation).
- **External Authenticated Actors**: Attempting privilege escalation, token substitution, IDOR (Insecure Direct Object Reference) on linked accounts.
- **Compromised Sessions**: Tokens stolen via XSS, malware, or network sniffing (if TLS fails).

## 3. Defense Mechanisms

### 3.1 Authentication & Token Lifecycle
- **Access Tokens (JWT)**: Short-lived (15 mins), stateless, signed using asymmetric cryptography (RS256).
- **Refresh Tokens (Opaque)**: Long-lived, stored securely in the database as salted hashes. Monitored for anomaly and reuse.
- **Token Substitution Defense**: Tokens are strictly tied to specific tenant IDs, user IDs, and session IDs.
- **Session Revocation**: A refresh token reuse triggers an immediate cascade revocation of the entire token family (compromised session defense).

### 3.2 WebAuthn (Passkeys) Architecture
- **Origin & RP ID Binding**: Strictly enforced. Phishing attempts on alternative domains will automatically fail cryptographic checks.
- **Replay Protection**: The `sign_count` is tracked per authenticator. A decreasing or stagnant `sign_count` on a non-cloned device triggers a lockout.
- **User Verification**: `require_user_verification=True` is enforced. A biometric or PIN check is strictly required, preventing physical "tap-only" theft.

### 3.3 OAuth2 Integration Security
- **OAuth CSRF Defense**: The OAuth `state` parameter is explicitly bound to a secure, HttpOnly, SameSite=Lax cookie generated at the initiation of the flow.
- **Account Linking Safety**: Unlinking an account requires "Step-up Auth" to ensure the actor is actively present and authorized.

### 3.4 Rate Limiting & Brute-force Prevention
- **Layered Rate Limiting**: Implemented via Redis at multiple layers (Tenant Global, IP-based, User-based, and Token-based).
- **Timing Attacks**: Sensitive cryptographic comparisons (e.g., password hashing, token validation) use constant-time algorithms.

## 4. Step-up Authentication Policy
MFA is treated as a core system policy.
- **Freshness Policy**: Sensitive actions (e.g., password resets, deleting linked accounts, exporting data) require the JWT to have an `auth_time` within the last 10 minutes.
- **Risk-based Anomalies**: Geolocation or IP/User-Agent changes trigger an automatic invalidation of long-lived sessions, requiring explicit 2FA re-verification.
