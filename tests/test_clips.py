from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pytest

from fmvcore import clips
from fmvcore.testing import seeded

FAKE = seeded()
FILM = FAKE.file_name(extension="mp4")
FETCH = "make fetch-the-films"
REQUIRE_ENV = "FMVCORE_TEST_CLIPS_REQUIRED"


@dataclass(frozen=True, slots=True)
class Entry:
    key: str = "trailer"
    title: str = "A trailer"
    url: str | None = "https://example.invalid/trailer.webm"
    file: str = "trailer.webm"
    committed: bool = False
    bytes: int | None = None
    sha256: str | None = None


def pinned_to(payload: bytes) -> Entry:
    return Entry(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())


class TestDigests:
    def test_every_digest_names_the_same_bytes(self):
        # Arrange
        payload = b"abc"

        # Act
        found = clips.digests(payload)

        # Assert
        assert found == {
            "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            "sha1": "a9993e364706816aba3e25717850c26c9cd0d89d",
            "crc32": "352441C2",
        }


class TestVerification:
    def test_a_matching_file_passes(self, tmp_path):
        # Arrange
        payload = FAKE.binary(length=38)
        path = tmp_path / FILM
        path.write_bytes(payload)

        # Act
        verdict = clips.verify(path, pinned_to(payload), fetch_command=FETCH)

        # Assert
        assert verdict == clips.Verdict(True, f"{FILM} matches A trailer")

    def test_a_wrong_size_is_named_as_the_wrong_file(self, tmp_path):
        # Arrange
        path = tmp_path / FILM
        path.write_bytes(b"short")
        entry = Entry(bytes=999, sha256="0" * 64)

        # Act
        verdict = clips.verify(path, entry, fetch_command=FETCH)

        # Assert
        assert verdict.ok is False
        assert verdict.diagnosis.startswith(f"{FILM} is 5 bytes and A trailer is 999.")

    def test_a_right_size_with_wrong_content_is_named_as_altered(self, tmp_path):
        # Arrange
        payload = b"x" * 32
        path = tmp_path / FILM
        path.write_bytes(payload)
        entry = Entry(bytes=len(payload), sha256="0" * 64)

        # Act
        verdict = clips.verify(path, entry, fetch_command=FETCH)

        # Assert
        assert verdict.ok is False
        assert verdict.diagnosis.startswith(f"{FILM} is the right length and the wrong content")

    def test_a_mismatch_prints_what_the_file_actually_is(self, tmp_path):
        # Arrange
        payload = b"y" * 32
        path = tmp_path / FILM
        path.write_bytes(payload)
        entry = Entry(bytes=len(payload), sha256="0" * 64)

        # Act
        verdict = clips.verify(path, entry, fetch_command=FETCH)

        # Assert
        assert f"found  sha256 {hashlib.sha256(payload).hexdigest()}" in verdict.diagnosis

    def test_an_absent_file_says_how_to_get_it(self, tmp_path):
        # Arrange
        path = tmp_path / "absent.mp4"

        # Act
        verdict = clips.verify(path, Entry(bytes=1, sha256="0" * 64), fetch_command=FETCH)

        # Assert
        assert verdict == clips.Verdict(False, f"{path} is not here. Fetch it with:\n    {FETCH}")

    def test_a_film_with_no_digest_is_refused_because_nothing_can_recognise_it(self, tmp_path):
        # Arrange
        path = tmp_path / FILM
        path.write_bytes(b"anything")

        # Act
        verdict = clips.verify(path, Entry(sha256=None), fetch_command=FETCH)

        # Assert
        assert verdict.ok is False
        assert verdict.diagnosis.startswith("the manifest publishes no digest for trailer")

    def test_wrong_content_with_no_published_size_is_not_called_the_right_length(self, tmp_path):
        # Arrange
        path = tmp_path / FILM
        path.write_bytes(b"not the film")

        # Act
        verdict = clips.verify(path, Entry(sha256="0" * 64), fetch_command=FETCH)

        # Assert
        assert verdict.diagnosis.startswith(f"{FILM} has the wrong content, which means")


class TestRequired:
    @pytest.mark.parametrize("value", ["1", "true", "YES", " yes "])
    def test_an_affirmative_value_requires_the_films(self, monkeypatch, value):
        # Arrange
        monkeypatch.setenv(REQUIRE_ENV, value)

        # Act
        result = clips.required(REQUIRE_ENV)

        # Assert
        assert result is True

    @pytest.mark.parametrize("value", ["", "0", "no", "later"])
    def test_anything_else_leaves_them_optional(self, monkeypatch, value):
        # Arrange
        monkeypatch.setenv(REQUIRE_ENV, value)

        # Act
        result = clips.required(REQUIRE_ENV)

        # Assert
        assert result is False

    def test_an_unset_variable_leaves_them_optional(self, monkeypatch):
        # Arrange
        monkeypatch.delenv(REQUIRE_ENV, raising=False)

        # Act
        result = clips.required(REQUIRE_ENV)

        # Assert
        assert result is False
