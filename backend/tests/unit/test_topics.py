from __future__ import annotations

from types import SimpleNamespace

from app.services.topics import deterministic_topics


def _material(title: str, section_titles: list[str]):
    sections = [SimpleNamespace(title=t, content=t * 10) for t in section_titles]
    return SimpleNamespace(id=1, title=title, sections=sections)


def test_deterministic_topics_uses_title_tokens():
    material = _material("Pythagorean Theorem Basics", ["Right triangles", "The hypotenuse rule"])
    topics = deterministic_topics(material)
    assert topics
    assert all(isinstance(t, str) and t == t.lower() for t in topics)
    joined = " ".join(topics)
    assert "pythagorean" in joined or "theorem" in joined


def test_deterministic_topics_excludes_stopwords():
    material = _material("An Introduction to the Core Ideas", ["This is the first section"])
    topics = deterministic_topics(material)
    assert "the" not in topics
    assert "an" not in topics
    assert topics, "should still produce some topics"


def test_deterministic_topics_falls_back_when_everything_is_stopwords():
    material = _material("The a an and or", [])
    topics = deterministic_topics(material)
    assert len(topics) >= 1
