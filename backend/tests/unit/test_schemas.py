"""Unit tests for Pydantic schema validation in app.schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import LoginRequest, MaterialCreate, QuizQuestionCreate, QuizSubmit, SectionCreate, UserCreate


class TestUserCreate:
    def test_valid_student(self) -> None:
        user = UserCreate(email="a@b.com", password="password-123", role="student")
        assert user.email == "a@b.com"

    def test_invalid_email(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password="password-123", role="student")

    def test_short_password_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(email="a@b.com", password="short", role="student")

    def test_invalid_role(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(email="a@b.com", password="password-123", role="admin")


class TestLoginRequest:
    def test_accepts_any_length_password(self) -> None:
        # login shouldn't enforce min length — that's user-facing UX concern
        req = LoginRequest(email="a@b.com", password="x")
        assert req.password == "x"


class TestSectionCreate:
    def test_defaults_order_to_zero(self) -> None:
        s = SectionCreate(title="T", content="C")
        assert s.order_index == 0


class TestMaterialCreate:
    def test_default_type_is_lesson(self) -> None:
        m = MaterialCreate(title="Title")
        assert m.type == "lesson"
        assert m.sections == []

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            MaterialCreate(title="T", type="podcast")


class TestQuizQuestionCreate:
    def test_defaults(self) -> None:
        q = QuizQuestionCreate(question="?", options=["a", "b"], correct_answer="a")
        assert q.points == 1.0


class TestQuizSubmit:
    def test_answers_keyed_by_string(self) -> None:
        submit = QuizSubmit(answers={"1": "A"})
        assert submit.answers["1"] == "A"

    def test_session_id_optional(self) -> None:
        submit = QuizSubmit(answers={})
        assert submit.session_id is None
