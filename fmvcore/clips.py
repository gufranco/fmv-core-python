from __future__ import annotations

import hashlib
import os
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

AFFIRMATIVE: Final = frozenset({"1", "true", "yes"})
CRC_MASK: Final = 0xFFFFFFFF


class Film(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def url(self) -> str | None: ...

    @property
    def file(self) -> str: ...

    @property
    def committed(self) -> bool: ...

    @property
    def bytes(self) -> int | None: ...

    @property
    def sha256(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class Verdict:
    ok: bool
    diagnosis: str


def digests(payload: bytes) -> dict[str, str]:
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "sha1": hashlib.sha1(payload).hexdigest(),
        "crc32": f"{zlib.crc32(payload) & CRC_MASK:08X}",
    }


def verify(path: Path, film: Film, *, fetch_command: str) -> Verdict:
    if not path.is_file():
        return Verdict(False, f"{path} is not here. Fetch it with:\n    {fetch_command}")

    if film.sha256 is None:
        return Verdict(
            False,
            f"the manifest publishes no digest for {film.key}, so no copy of it can be "
            "recognised; add its sha256 and bytes to the manifest",
        )

    wrong_size = _size_mismatch(path, film, fetch_command)
    if wrong_size is not None:
        return wrong_size
    return _digest_verdict(path, film, fetch_command)


def required(variable: str) -> bool:
    return os.environ.get(variable, "").strip().lower() in AFFIRMATIVE


def _size_mismatch(path: Path, film: Film, fetch_command: str) -> Verdict | None:
    size = path.stat().st_size
    if film.bytes is None or size == film.bytes:
        return None
    return Verdict(
        False,
        f"{path.name} is {size} bytes and {film.title} is {film.bytes}. "
        "The size decides before the digest does, so this is a different file "
        "rather than a damaged one. Delete it and fetch again with:\n"
        f"    {fetch_command}",
    )


def _digest_verdict(path: Path, film: Film, fetch_command: str) -> Verdict:
    found = digests(path.read_bytes())
    if found["sha256"] == film.sha256:
        return Verdict(True, f"{path.name} matches {film.title}")
    shape = "is the right length and" if film.bytes is not None else "has"
    return Verdict(
        False,
        f"{path.name} {shape} the wrong content, which means "
        "the copy was re-encoded, re-muxed, truncated or corrupted rather than "
        f"being a different film.\n    wanted sha256 {film.sha256}\n"
        f"    found  sha256 {found['sha256']}\n"
        f"    found  crc32  {found['crc32']}\n"
        f"Search that digest to identify the copy, then fetch again with:\n"
        f"    {fetch_command}",
    )
