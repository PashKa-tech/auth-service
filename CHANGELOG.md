# Changelog

All notable changes to the OmniAuth Service (Enterprise Auth Service) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Multi-tenant Core**: Full isolated organization support via B2B SaaS tenant model.
- **Passkeys (WebAuthn)**: Out-of-the-box passwordless biometric logins (FaceID, TouchID, YubiKey).
- **OAuth Providers**: 7 native OAuth 2.0 integrations (Google, GitHub, Apple, Facebook, Discord, Twitter, Amazon).
- **Rate Limiting Engine**: Scalable Redis-backed SlowAPI implementation with negative caching to prevent fail-open vulnerabilities.
- **Webhook Dispatch**: Secure async Webhook delivery to remote tenant endpoints via `BackgroundTasks` with SSRF protection.
- **Audit Logs**: Granular logging of security-critical actions (login, password reset, 2FA setup, OAuth link).
- **Frontend Dashboard**: Sleek React UI with Framer Motion animations, glassmorphism design, and global Toast notifications.
- **Automated CAPTCHA**: Native reCAPTCHA v3 checking with fail-closed server-side verification and fallback custom SVG captcha.

### Changed
- Refactored `RoleChecker` and `RateLimiter` to operate consistently via Dependency Injection in FastAPI routers.
- Transitioned DB queries in feature layers (RBAC, Webhooks, Actions) to the structured Repository Pattern for robust unit testing.
- Overhauled API Client (`api.ts`) to use Axios with response interceptors for fully automated JWT refresh cycles and 401/403 event dispatching.
- Expanded project documentation (`README.md` and `ARCHITECTURE.md`) to be entirely bilingual (English and Russian).

### Fixed
- Fixed silent data loss bugs where `await db.commit()` was missing in critical mutation operations (e.g. `login_user`, passwordless tokens).
- Fixed double logout dispatch in `Layout.tsx` and `useAuth.ts` which caused redundant backend API requests.
- Fixed Apple OAuth token validation to enforce cryptographically secure `PyJWKClient` verification against Apple's live public keys.
- Corrected SSRF attack vector on webhooks by enforcing strict local-IP resolution checks before dispatch.
