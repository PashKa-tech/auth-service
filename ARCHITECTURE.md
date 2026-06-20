# 🏛️ Architecture Overview

This document provides a high-level overview of the OmniAuth Service architecture, highlighting our database schema design and the flow of critical authentication requests.

---

## Database Schema

Our database is designed around a multi-tenant model. Every entity is tenant-aware, ensuring strict data isolation across different organizations using the service.

```mermaid
erDiagram
    TENANT {
        uuid id PK
        string name
        string domain
        string branding_logo_url
        string theme_colors
        datetime created_at
    }
    
    USER {
        uuid id PK
        uuid tenant_id FK
        string email
        string password_hash
        boolean is_active
        boolean mfa_enabled
        string webauthn_credentials
        datetime created_at
    }
    
    SESSION {
        uuid id PK
        uuid user_id FK
        string refresh_token
        string ip_address
        string user_agent
        datetime expires_at
    }
    
    AUDIT_LOG {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        string action
        string resource
        jsonb metadata
        datetime timestamp
    }

    TENANT ||--o{ USER : "owns"
    TENANT ||--o{ AUDIT_LOG : "records"
    USER ||--o{ SESSION : "has"
    USER ||--o{ AUDIT_LOG : "triggers"
```

### Key Entities

- **TENANT**: Represents an organization or isolated instance within the Auth Service.
- **USER**: The individuals authenticating against a tenant. Includes support for traditional passwords and Passkeys (WebAuthn).
- **SESSION**: Tracks active user sessions, storing refresh tokens and client metadata for anomaly detection.
- **AUDIT_LOG**: Immutable ledger of all security events and administrative actions for compliance and monitoring.

---

## Authentication Flows

### Login Request Flow (with 2FA / Passkeys)

The authentication process seamlessly supports Password + 2FA or passwordless WebAuthn (Passkeys) while evaluating bot risks via Captcha.

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Frontend as React SPA
    participant API as FastAPI Backend
    participant Cache as Redis
    participant DB as PostgreSQL
    participant Captcha as Captcha Provider

    Client->>Frontend: Initiates Login
    
    alt WebAuthn (Passkeys)
        Frontend->>API: Request WebAuthn Challenge
        API-->>Frontend: Challenge + Options
        Frontend->>Client: Prompt Biometrics/Security Key
        Client-->>Frontend: Signed Assertion
        Frontend->>API: Verify Assertion
        API->>DB: Validate User & Credentials
    else Standard Password
        Frontend->>API: POST /login (Email, Password, Captcha Token)
        API->>Captcha: Verify Token
        Captcha-->>API: Risk Score
        API->>DB: Verify Email & Password Hash
        alt 2FA Enabled
            API-->>Frontend: 2FA Required Token
            Frontend->>Client: Prompt for TOTP/SMS Code
            Client-->>Frontend: Enter Code
            Frontend->>API: Verify 2FA Code
        end
    end
    
    API->>DB: Generate Session & Refresh Token
    API->>Cache: Cache Session Data
    API->>DB: Write Audit Log (Login Success)
    API-->>Frontend: Return Access Token & Refresh Token
    Frontend-->>Client: Authenticated State
```

### Flow Breakdown

1. **Initialization**: The client application begins the login process.
2. **Path Selection**: Based on the user's setup and preference, the flow branches to either WebAuthn or Password-based login.
3. **WebAuthn**: 
   - A cryptographic challenge is issued.
   - The user signs the challenge with their device authenticator (Passkey).
   - The backend verifies the signature against the public key stored in the database.
4. **Standard Password + 2FA**:
   - The initial request is vetted by the Captcha provider to block bot traffic.
   - Credentials are verified.
   - If MFA is enabled, an intermediate token is issued, and the user must provide a TOTP or SMS code to finalize the login.
5. **Session Finalization**: Upon successful verification, tokens are issued, caching is updated for fast authorization, and an audit log is recorded for security monitoring.
