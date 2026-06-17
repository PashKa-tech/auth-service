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
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./dev.db")
    
    # Caching / Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    USE_FAKEREDIS: bool = True  # Default to True for simple development/test setup
    
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
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str | None = Field(default=None)
    GOOGLE_CLIENT_SECRET: str | None = Field(default=None)
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:8000/api/v1/auth/oauth/google/callback")
    
    # GitHub OAuth
    GITHUB_CLIENT_ID: str | None = Field(default=None)
    GITHUB_CLIENT_SECRET: str | None = Field(default=None)
    GITHUB_REDIRECT_URI: str = Field(default="http://localhost:8000/api/v1/auth/oauth/github/callback")
    
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env.dev"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
