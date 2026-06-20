import base64
from cryptography.fernet import Fernet
import pyotp
import secrets
import hashlib
from src.config import settings
from src.core.logging import logger

# Initialize Fernet key
_key = settings.TOTP_ENCRYPTION_KEY
if not _key:
    if settings.ENV == "production":
        raise RuntimeError("TOTP_ENCRYPTION_KEY must be set in production environment!")
    # Auto-generate key for dev/testing if not configured
    logger.warning("TOTP_ENCRYPTION_KEY is not set. Generating a temporary key for this run. Do not use this in production!")
    _key = Fernet.generate_key().decode()
    settings.TOTP_ENCRYPTION_KEY = _key

try:
    # Ensure key is valid Fernet key
    fernet = Fernet(_key.encode())
except Exception as e:
    if settings.ENV == "production":
        raise RuntimeError(f"Invalid TOTP_ENCRYPTION_KEY format in production: {str(e)}")
    logger.error(f"Invalid TOTP_ENCRYPTION_KEY format. Generating a fallback key. Error: {str(e)}")
    fernet = Fernet(Fernet.generate_key())

def encrypt_secret(secret: str) -> str:
    """Encrypt a TOTP secret using Fernet."""
    return fernet.encrypt(secret.encode()).decode()

def decrypt_secret(encrypted_secret: str) -> str:
    """Decrypt a TOTP secret using Fernet."""
    return fernet.decrypt(encrypted_secret.encode()).decode()

def generate_totp_secret() -> str:
    """Generate a random Base32 TOTP secret (160 bits of entropy)."""
    return pyotp.random_base32()

def get_provisioning_uri(secret: str, email: str) -> str:
    """Get the provisioning URI for Google Authenticator QR Code."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name=settings.TOTP_ISSUER_NAME
    )

def verify_totp_code(secret: str, code: str) -> bool:
    """Verify a TOTP code with time drift window."""
    totp = pyotp.totp.TOTP(secret)
    # valid_window=1 allows current time step, previous one, and next one (handles minor clock drift)
    return totp.verify(code.strip(), valid_window=1)

def generate_backup_codes() -> list[str]:
    """Generate a list of secure, random alphanumeric backup codes."""
    codes = []
    for _ in range(settings.BACKUP_CODES_COUNT):
        # Generate random 8-character string containing letters and digits
        # Excluding confusing characters like O, 0, I, 1
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        codes.append(code)
    return codes

def hash_backup_code(code: str) -> str:
    """Hash a backup code using SHA-256 for secure storage."""
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()
