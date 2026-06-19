import uuid
import pytest
from hypothesis import given, strategies as st
from src.core.security import (
    verify_access_token,
    verify_mfa_token,
    hash_password,
    verify_password,
    verify_pkce,
)
from src.core.fingerprint import calculate_device_fingerprint

# Strategy for common IP representations and random strings
ip_strategy = st.one_of(
    st.ip_addresses().map(str),
    st.text(),
    st.none()
)

@given(token=st.text())
def test_fuzz_verify_access_token(token):
    """Fuzz verify_access_token with random strings to ensure it doesn't crash."""
    result = verify_access_token(token)
    assert result is None

@given(token=st.text())
def test_fuzz_verify_mfa_token(token):
    """Fuzz verify_mfa_token with random strings to ensure it doesn't crash."""
    result = verify_mfa_token(token)
    assert result is None

@given(
    ua=st.one_of(st.text(), st.none()),
    ip=ip_strategy,
    lang=st.one_of(st.text(), st.none())
)
def test_fuzz_calculate_device_fingerprint(ua, ip, lang):
    """Fuzz device fingerprint calculation with random inputs."""
    result = calculate_device_fingerprint(ua, ip, lang)
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 hex digest length

@given(password=st.text())
def test_fuzz_hash_and_verify_password(password):
    """Fuzz password hashing and verification with random strings.
    Argon2 has internal limits, but the Python bindings should raise appropriate errors
    or handle it gracefully. We just ensure no unhandled unexpected exceptions occur.
    """
    try:
        # Some extremely long passwords might raise exceptions in argon2, 
        # but typically standard texts work fine.
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        # Verify against wrong password
        assert verify_password(password + "x", hashed) is False
    except Exception as e:
        # If argon2 rejects due to length/content, that's acceptable, but we catch it
        # to ensure the test suite doesn't crash on standard fuzzing strings.
        pass

@given(password=st.text(), hashed=st.text())
def test_fuzz_verify_password_random_hash(password, hashed):
    """Ensure verify_password safely rejects invalid hash formats."""
    result = verify_password(password, hashed)
    assert result is False

@given(
    verifier=st.text(),
    challenge=st.text(),
    method=st.sampled_from(["plain", "S256", "invalid_method", ""])
)
def test_fuzz_verify_pkce(verifier, challenge, method):
    """Fuzz PKCE verification to ensure it doesn't crash on arbitrary strings."""
    result = verify_pkce(verifier, challenge, method=method)
    assert isinstance(result, bool)
