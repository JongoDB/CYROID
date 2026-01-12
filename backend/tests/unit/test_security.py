# backend/tests/unit/test_security.py
import pytest
from uuid import uuid4

from cyroid.utils.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)


def test_password_hashing():
    password = "testpassword123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_access_token_creation_and_decoding():
    user_id = uuid4()
    token = create_access_token(user_id)

    decoded_id = decode_access_token(token)
    assert decoded_id == user_id


def test_invalid_token_returns_none():
    result = decode_access_token("invalid.token.here")
    assert result is None
