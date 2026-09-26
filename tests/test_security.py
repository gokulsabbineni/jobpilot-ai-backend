import base64
import hashlib
import hmac

import pytest

from app.security import hash_password, verify_password, create_access_token, decode_token


def test_password_hash_round_trip():
    encoded = hash_password("correct horse battery staple")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_password_hashes_are_salted():
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second


def test_access_token_contains_user_identity():
    token = create_access_token(123, "USER")
    payload = decode_token(token)
    assert payload["sub"] == "123"
    assert payload["role"] == "USER"
    assert "exp" in payload


def test_invalid_token_is_rejected():
    with pytest.raises(Exception):
        decode_token("not-a-valid-token")
