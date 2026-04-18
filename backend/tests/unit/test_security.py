"""Unit tests for app.security: password hashing + JWT encode/decode."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.security import create_token, decode_token, hash_password, verify_password
from app.settings import get_settings


class TestPasswordHashing:
    def test_hash_round_trip(self) -> None:
        hashed = hash_password("correct horse battery")
        assert verify_password("correct horse battery", hashed) is True

    def test_wrong_password_rejected(self) -> None:
        hashed = hash_password("original")
        assert verify_password("different", hashed) is False

    def test_hash_is_salted(self) -> None:
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        assert verify_password("same-password", h1)
        assert verify_password("same-password", h2)

    def test_empty_password_roundtrip(self) -> None:
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("x", hashed) is False


class TestTokenCreation:
    def test_access_token_decodes(self) -> None:
        token = create_token("42", "access")
        payload = decode_token(token, "access")
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_refresh_token_decodes(self) -> None:
        token = create_token("99", "refresh")
        payload = decode_token(token, "refresh")
        assert payload["sub"] == "99"
        assert payload["type"] == "refresh"

    def test_access_token_rejected_as_refresh(self) -> None:
        token = create_token("1", "access")
        with pytest.raises(ValueError, match="Invalid token type"):
            decode_token(token, "refresh")

    def test_refresh_token_rejected_as_access(self) -> None:
        token = create_token("1", "refresh")
        with pytest.raises(ValueError, match="Invalid token type"):
            decode_token(token, "access")

    def test_tampered_signature(self) -> None:
        token = create_token("1", "access")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token(tampered, "access")

    def test_invalid_string(self) -> None:
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token("not-a-jwt", "access")

    def test_expired_token(self) -> None:
        settings = get_settings()
        expired = jwt.encode(
            {"sub": "1", "type": "access", "exp": datetime.now(UTC) - timedelta(seconds=10)},
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token(expired, "access")

    def test_missing_subject_rejected(self) -> None:
        settings = get_settings()
        bad_token = jwt.encode(
            {"type": "access", "exp": datetime.now(UTC) + timedelta(minutes=1)},
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(ValueError, match="subject"):
            decode_token(bad_token, "access")

    def test_access_expires_later_than_now(self) -> None:
        token = create_token("1", "access")
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["exp"] > int(datetime.now(UTC).timestamp())

    def test_refresh_lives_longer_than_access(self) -> None:
        access = create_token("1", "access")
        refresh = create_token("1", "refresh")
        settings = get_settings()
        a = jwt.decode(access, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        r = jwt.decode(refresh, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert r["exp"] > a["exp"]
