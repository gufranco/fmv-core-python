from __future__ import annotations

import http.client
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Final, Protocol

from fmvcore import clips

CHUNK: Final = 1 << 20
TIMEOUT: Final = 300
MAX_BLOCKS: Final = 1 << 12
PARTIAL_SUFFIX: Final = ".part"
ATTEMPTS: Final = 3
BACKOFF_SECONDS: Final = 5.0
TRANSIENT: Final = (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException)

Download = Callable[[str, Path, int | None], None]
Wait = Callable[[float], None]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Outcome:
    key: str
    action: str
    ok: bool
    diagnosis: str


class TooLargeError(RuntimeError):
    pass


class _Source(Protocol):
    def read(self, amount: int, /) -> bytes: ...


def downloader(user_agent: str, *, chunk: int = CHUNK, max_blocks: int = MAX_BLOCKS) -> Download:
    def download(url: str, target: Path, limit: int | None) -> None:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        target.parent.mkdir(parents=True, exist_ok=True)
        with (
            urllib.request.urlopen(request, timeout=TIMEOUT) as response,
            target.open("wb") as sink,
        ):
            _copy(response, sink, url=url, limit=limit, chunk=chunk, max_blocks=max_blocks)

    return download


def fetch(url: str, target: Path, limit: int | None, *, download: Download, wait: Wait) -> None:
    for attempt in range(1, ATTEMPTS + 1):
        try:
            download(url, target, limit)
        except TRANSIENT as error:
            if attempt == ATTEMPTS:
                raise
            logger.warning("%s: %r; retrying, attempt %d of %d", url, error, attempt + 1, ATTEMPTS)
            wait(BACKOFF_SECONDS * attempt)
        else:
            return


def acquire(
    film: clips.Film,
    target: Path,
    *,
    fetch_command: str,
    download: Download,
    wait: Wait = time.sleep,
) -> Outcome:
    held = _already_held(film, target, fetch_command)
    if held is not None:
        return held
    if not film.url:
        return Outcome(film.key, "unreachable", False, f"{film.key} has no url in the manifest")

    partial = target.with_name(target.name + PARTIAL_SUFFIX)
    try:
        fetch(film.url, partial, film.bytes, download=download, wait=wait)
    except (*TRANSIENT, TooLargeError) as error:
        partial.unlink(missing_ok=True)
        return Outcome(film.key, "failed", False, f"{film.url}: {error}")
    verdict = clips.verify(partial, film, fetch_command=fetch_command)
    if not verdict.ok:
        partial.unlink(missing_ok=True)
        return Outcome(film.key, "rejected", False, verdict.diagnosis)
    partial.replace(target)
    return Outcome(film.key, "fetched", True, verdict.diagnosis)


def _copy(
    response: _Source,
    sink: IO[bytes],
    *,
    url: str,
    limit: int | None,
    chunk: int,
    max_blocks: int,
) -> None:
    ceiling = limit if limit is not None else 0
    written = 0
    for _ in range(max_blocks):
        block = response.read(chunk)
        if not block:
            return
        written += len(block)
        if ceiling and written > ceiling:
            msg = f"{url} sent more than the {ceiling} bytes the manifest names"
            raise TooLargeError(msg)
        sink.write(block)
    msg = f"{url} sent more than {max_blocks} blocks without ending"
    raise TooLargeError(msg)


def _already_held(film: clips.Film, target: Path, fetch_command: str) -> Outcome | None:
    if film.committed:
        verdict = clips.verify(target, film, fetch_command=fetch_command)
        return Outcome(film.key, "committed", verdict.ok, verdict.diagnosis)
    if target.is_file():
        verdict = clips.verify(target, film, fetch_command=fetch_command)
        if verdict.ok:
            return Outcome(film.key, "present", True, verdict.diagnosis)
    return None
