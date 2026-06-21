import os
import json
import base64
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from src.config import settings

CERTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "certs")
PRIVATE_KEY_PATH = os.path.join(CERTS_DIR, "private_key.pem")
PUBLIC_KEY_PATH = os.path.join(CERTS_DIR, "public_key.pem")

_private_key = None
_public_key = None
_jwks = None

def _int_to_base64url(value: int) -> str:
    """Convert an integer to a base64url-encoded string (required for JWK)."""
    val_bytes = value.to_bytes((value.bit_length() + 7) // 8, byteorder='big')
    return base64.urlsafe_b64encode(val_bytes).decode('utf-8').rstrip('=')

def get_rsa_keys():
    """Load or generate RSA keys and cache them."""
    global _private_key, _public_key, _jwks
    
    if _private_key is not None:
        return _private_key, _public_key, _jwks
        
    if getattr(settings, "JWT_PRIVATE_KEY_PEM", None) and getattr(settings, "JWT_PUBLIC_KEY_PEM", None):
        _private_key = serialization.load_pem_private_key(
            settings.JWT_PRIVATE_KEY_PEM.encode("utf-8"),
            password=None,
            backend=default_backend()
        )
        _public_key = serialization.load_pem_public_key(
            settings.JWT_PUBLIC_KEY_PEM.encode("utf-8"),
            backend=default_backend()
        )
    else:
        # Fallback to local files for development
        os.makedirs(CERTS_DIR, exist_ok=True)
        
        if not os.path.exists(PRIVATE_KEY_PATH):
            import logging
            logging.getLogger(__name__).warning(
                "JWT_PRIVATE_KEY_PEM not found in environment. "
                "Generating new local RSA keys. WARNING: This breaks horizontal scaling!"
            )
            # Generate new RSA key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            public_key = private_key.public_key()
            
            with open(PRIVATE_KEY_PATH, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
                
            with open(PUBLIC_KEY_PATH, "wb") as f:
                f.write(public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
                
        # Load keys
        with open(PRIVATE_KEY_PATH, "rb") as f:
            _private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
            
        with open(PUBLIC_KEY_PATH, "rb") as f:
            _public_key = serialization.load_pem_public_key(
                f.read(),
                backend=default_backend()
            )
        
    # Generate JWKS
    pn = _public_key.public_numbers()
    
    _jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "auth-service-key-1", # Hardcoded key ID for now
                "use": "sig",
                "alg": "RS256",
                "n": _int_to_base64url(pn.n),
                "e": _int_to_base64url(pn.e),
            }
        ]
    }
    
    return _private_key, _public_key, _jwks

# Call once to initialize on import
get_rsa_keys()
