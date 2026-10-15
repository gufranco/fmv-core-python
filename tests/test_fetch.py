from __future__ import annotations

import hashlib
import http.client
import urllib.error
from dataclasses import dataclass
from pathlib import Path

import pytest

from fmvcore import fetch
from fmvcore.testing import seeded

FAKE = seeded()
PRETEND_FILM = FAKE.binary(length=12)
JUNK = FAKE.binary(length=4)
SENT = FAKE.binary(length=10)
OVERLONG = FAKE.binary(length=24)
FETCH = "make fetch-the-films"
URL = "https://example.invalid/film"


@dataclass(frozen=True, slots=True)
class Entry:
    key: str = "trailer"
    title: str = "A trailer"
    url: str | None = URL
    file: str = "trailer.webm"
    committed: bool = False
    bytes: int | None = None
    sha256: str | None = None


def pinned_to(payload: bytes, **changes: object) -> Entry:
    return Entry(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), **changes)


def writes(payload: bytes):
    return lambda _url, target, _limit: target.write_bytes(payload)


def never(_url: str, _target: Path, _limit: int | None) -> None:
    msg = "this case must not download"
    raise AssertionError(msg)


def unreachable(url: str, _target: Path, _limit: int | None) -> None:
    raise urllib.error.URLError(f"cannot reach {url}")


def oversized(url: str, target: Path, _limit: int | None) -> None:
    target.write_bytes(b"partial")
    msg = f"{url} sent too much"
    raise fetch.TooLargeError(msg)


def no_wait(_seconds: float) -> None:
    return None


class Flaky:
    def __init__(self, error: Exception, *, failures: int) -> None:
        self.error = error
        self.failures = failures
        self.calls = 0

    def __call__(self, _url: str, target: Path, _limit: int | None) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        target.write_bytes(b"film")


class Waits:
    def __init__(self) -> None:
        self.seen: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seen = [*self.seen, seconds]


class TestAcquiring:
    def test_a_committed_film_is_checked_and_never_downloaded(self, tmp_path):
        # Arrange
        target = tmp_path / "trailer.webm"
        target.write_bytes(PRETEND_FILM)
        entry = pinned_to(PRETEND_FILM, committed=True)

        # Act
        outcome = fetch.acquire(entry, target, fetch_command=FETCH, download=never)

        # Assert
        assert (outcome.action, outcome.ok) == ("committed", True)

    def test_a_committed_film_that_has_changed_is_refused(self, tmp_path):
        # Arrange
        target = tmp_path / "trailer.webm"
        target.write_bytes(PRETEND_FILM)
        entry = Entry(committed=True, bytes=len(PRETEND_FILM), sha256="0" * 64)

        # Act
        outcome = fetch.acquire(entry, target, fetch_command=FETCH, download=never)

        # Assert
        assert (outcome.action, outcome.ok) == ("committed", False)

    def test_a_film_already_verified_is_kept(self, tmp_path):
        # Arrange
        target = tmp_path / "trailer.webm"
        target.write_bytes(PRETEND_FILM)

        # Act
        outcome = fetch.acquire(
            pinned_to(PRETEND_FILM), target, fetch_command=FETCH, download=never
        )

        # Assert
        assert outcome.action == "present"

    def test_an_absent_film_is_downloaded(self, tmp_path):
        # Arrange
        target = tmp_path / "trailer.webm"

        # Act
        outcome = fetch.acquire(
            pinned_to(PRETEND_FILM), target, fetch_command=FETCH, download=writes(PRETEND_FILM)
        )

        # Assert
        assert (outcome.action, outcome.ok, target.read_bytes()) == ("fetched", True, PRETEND_FILM)

    def test_a_stale_copy_is_replaced_rather_than_kept(self, tmp_path):
        # Arrange
        target = tmp_path / "trailer.webm"
        target.write_bytes(b"an older cut")

        # Act
        outcome = fetch.acquire(
            pinned_to(PRETEND_FILM), target, fetch_command=FETCH, download=writes(PRETEND_FILM)
        )

        # Assert
        assert (outcome.action, target.read_bytes()) == ("fetched", PRETEND_FILM)

    def test_a_film_with_no_url_cannot_be_fetched(self, tmp_path):
        # Arrange
        entry = Entry(url=None)

        # Act
        outcome = fetch.acquire(
            entry, tmp_path / "trailer.webm", fetch_command=FETCH, download=never
        )

        # Assert
        assert outcome == fetch.Outcome(
            "trailer", "unreachable", False, "trailer has no url in the manifest"
        )


class TestAFailedAcquisition:
    def test_a_bad_download_is_refused_says_what_arrived_and_leaves_nothing(self, tmp_path):
        # Arrange
        entry = Entry(bytes=4, sha256="0" * 64)

        # Act
        outcome = fetch.acquire(
            entry, tmp_path / "trailer.webm", fetch_command=FETCH, download=writes(JUNK)
        )

        # Assert
        assert outcome.action == "rejected"
        assert hashlib.sha256(JUNK).hexdigest() in outcome.diagnosis
        assert list(tmp_path.iterdir()) == []

    def test_a_network_failure_is_reported_and_leaves_nothing(self, tmp_path):
        # Arrange
        entry = pinned_to(PRETEND_FILM)

        # Act
        outcome = fetch.acquire(
            entry,
            tmp_path / "trailer.webm",
            fetch_command=FETCH,
            download=unreachable,
            wait=no_wait,
        )

        # Assert
        assert outcome.action == "failed"
        assert list(tmp_path.iterdir()) == []

    def test_an_oversized_download_is_refused_and_leaves_nothing(self, tmp_path):
        # Arrange
        entry = pinned_to(PRETEND_FILM)

        # Act
        outcome = fetch.acquire(
            entry, tmp_path / "trailer.webm", fetch_command=FETCH, download=oversized, wait=no_wait
        )

        # Assert
        assert outcome == fetch.Outcome("trailer", "failed", False, f"{URL}: {URL} sent too much")
        assert list(tmp_path.iterdir()) == []


class TestTheDownload:
    def test_it_copies_what_the_server_sends(self, tmp_path):
        # Arrange
        source = tmp_path / "source.bin"
        source.write_bytes(SENT)
        target = tmp_path / "copy.bin"

        # Act
        fetch.downloader("fmvcore-tests/1.0")(source.as_uri(), target, 10)

        # Assert
        assert target.read_bytes() == SENT

    def test_it_stops_at_the_size_the_manifest_names(self, tmp_path):
        # Arrange
        source = tmp_path / "source.bin"
        source.write_bytes(OVERLONG)
        download = fetch.downloader("fmvcore-tests/1.0")

        # Act
        with pytest.raises(fetch.TooLargeError) as refused:
            download(source.as_uri(), tmp_path / "copy.bin", 10)

        # Assert
        assert str(refused.value) == (
            f"{source.as_uri()} sent more than the 10 bytes the manifest names"
        )

    def test_a_stream_that_never_ends_is_stopped(self, tmp_path):
        # Arrange
        source = tmp_path / "source.bin"
        source.write_bytes(bytes(12))
        download = fetch.downloader("fmvcore-tests/1.0", chunk=4, max_blocks=2)

        # Act
        with pytest.raises(fetch.TooLargeError) as refused:
            download(source.as_uri(), tmp_path / "copy.bin", None)

        # Assert
        assert str(refused.value) == f"{source.as_uri()} sent more than 2 blocks without ending"


class TestATransientFailure:
    def test_a_reset_connection_is_retried_until_it_lands(self, tmp_path):
        # Arrange
        flaky = Flaky(ConnectionResetError("reset by peer"), failures=2)
        target = tmp_path / "film.part"

        # Act
        fetch.fetch(URL, target, None, download=flaky, wait=no_wait)

        # Assert
        assert (flaky.calls, target.read_bytes()) == (3, b"film")

    def test_a_torn_read_on_every_attempt_gives_up_after_three(self, tmp_path):
        # Arrange
        flaky = Flaky(http.client.IncompleteRead(b"fi"), failures=9)
        waits = Waits()

        # Act
        with pytest.raises(http.client.IncompleteRead):
            fetch.fetch(URL, tmp_path / "film.part", None, download=flaky, wait=waits)

        # Assert
        assert (flaky.calls, waits.seen) == (3, [5.0, 10.0])

    def test_an_oversized_download_is_never_retried(self, tmp_path):
        # Arrange
        flaky = Flaky(fetch.TooLargeError("too big"), failures=9)

        # Act
        with pytest.raises(fetch.TooLargeError):
            fetch.fetch(URL, tmp_path / "film.part", None, download=flaky, wait=no_wait)

        # Assert
        assert flaky.calls == 1
