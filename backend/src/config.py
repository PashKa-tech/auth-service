import os
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    ENV: Literal["development", "testing", "production"] = "development"
    
    # Base URL / CORS
    APP_NAME: str = "Auth Service"
    API_V1_STR: str = "/api/v1/auth"
    
    # Database
    DATABASE_URL: str = Field(default="postgresql+asyncpg://user:password@localhost:5432/authdb")
    
    # Caching / Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    USE_FAKEREDIS: bool = False  # Changed default to False to use real Redis
    
    # Security/JWT (Secret Key for HS256)
    JWT_SECRET_KEY: str = Field(default="dev_jwt_secret_key_change_me_in_production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Argon2 Parameters
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 4
    
    # Super Admin / Provisioning
    SUPER_ADMIN_API_KEY: str = Field(default="super-admin-secret-key-change-me")
    
    # Domain configuration
    DOMAIN: str = "localhost"
    API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    
    # OAuth Provider Toggles
    ENABLE_GOOGLE_OAUTH: bool = Field(default=True)
    ENABLE_GITHUB_OAUTH: bool = Field(default=True)
    ENABLE_DISCORD_OAUTH: bool = False
    ENABLE_APPLE_OAUTH: bool = False
    ENABLE_FACEBOOK_OAUTH: bool = False
    ENABLE_TWITTER_OAUTH: bool = Field(default=True)
    ENABLE_AMAZON_OAUTH: bool = False
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str | None = Field(default=None)
    GOOGLE_CLIENT_SECRET: str | None = Field(default=None)
    GOOGLE_REDIRECT_URI: str | None = Field(default=None)
    
    # GitHub OAuth
    GITHUB_CLIENT_ID: str | None = Field(default=None)
    GITHUB_CLIENT_SECRET: str | None = Field(default=None)
    GITHUB_REDIRECT_URI: str | None = Field(default=None)
    
    # Discord OAuth
    DISCORD_CLIENT_ID: str | None = None
    DISCORD_CLIENT_SECRET: str | None = None
    DISCORD_REDIRECT_URI: str | None = Field(default=None)
    
    # Apple OAuth
    APPLE_CLIENT_ID: str | None = None
    APPLE_CLIENT_SECRET: str | None = None
    APPLE_REDIRECT_URI: str | None = Field(default=None)
    
    # Facebook OAuth
    FACEBOOK_CLIENT_ID: str | None = None
    FACEBOOK_CLIENT_SECRET: str | None = None
    FACEBOOK_REDIRECT_URI: str | None = Field(default=None)
    
    # Twitter (X) OAuth
    TWITTER_CLIENT_ID: str | None = Field(default=None)
    TWITTER_CLIENT_SECRET: str | None = Field(default=None)
    TWITTER_REDIRECT_URI: str | None = Field(default=None)
    
    # Amazon OAuth
    AMAZON_CLIENT_ID: str | None = None
    AMAZON_CLIENT_SECRET: str | None = None
    AMAZON_REDIRECT_URI: str | None = Field(default=None)
    
    # SMTP / Email Settings
    SMTP_HOST: str = Field(default="localhost")
    SMTP_PORT: int = Field(default=1025)
    SMTP_USER: str | None = Field(default=None)
    SMTP_PASSWORD: str | None = Field(default=None)
    SMTP_FROM_EMAIL: str = Field(default="noreply@authservice.com")
    USE_MOCK_EMAIL: bool = Field(default=True)
    
    # 2FA Settings
    TOTP_ENCRYPTION_KEY: str = Field(default="")  # Fernet key, auto-generated if empty
    TOTP_ISSUER_NAME: str = "AuthService"
    BACKUP_CODES_COUNT: int = 10
    MFA_TOKEN_EXPIRE_MINUTES: int = 5
    
    def get_redirect_uri(self, provider: str) -> str:
        return f"{self.API_BASE_URL}/api/v1/auth/oauth/{provider}/callback"

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env.dev"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
