from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Final

SECONDS_PER_HOUR: Final = 3600
SECONDS_PER_MINUTE: Final = 60
MILLIS_DIGITS: Final = 3
MILLIS_PER_SECOND: Final = 1000.0
TIMING: Final = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)
MARKUP: Final = re.compile(r"<[^>]+>|\{[^}]*\}")
BLOCK_GAP: Final = re.compile(r"\n\s*\n")


@dataclass(frozen=True, slots=True)
class Cue:
    start: float
    end: float
    lines: tuple[str, ...]


def sidecar_for(source: Path) -> Path | None:
    candidate = Path(source).with_suffix(".srt")
    return candidate if candidate.is_file() else None


def parse(text: str) -> list[Cue]:
    blocks = BLOCK_GAP.split(text.replace("\r\n", "\n").strip())
    return [cue for cue in (_cue(block) for block in blocks) if cue is not None]


def trimmed(cues: list[Cue]) -> list[Cue]:
    ordered = sorted(cues, key=lambda cue: (cue.start, cue.end))
    ends = [
        min(cue.end, ordered[index + 1].start) if index + 1 < len(ordered) else cue.end
        for index, cue in enumerate(ordered)
    ]
    return [
        Cue(start=cue.start, end=end, lines=cue.lines)
        for cue, end in zip(ordered, ends, strict=True)
        if end > cue.start
    ]


def active(cues: list[Cue], seconds: float) -> Cue | None:
    return next((cue for cue in cues if cue.start <= seconds < cue.end), None)


def layout(text: str, *, columns: int, max_lines: int) -> tuple[str, ...]:
    if columns < 1 or max_lines < 1:
        msg = f"a subtitle needs at least one column and one line, got {columns}x{max_lines}"
        raise ValueError(msg)
    wrapped = textwrap.wrap(text, width=columns, break_long_words=True) or [""]
    return tuple(line[:columns] for line in wrapped[:max_lines])


def _seconds(hours: str, minutes: str, secs: str, millis: str) -> float:
    whole = int(hours) * SECONDS_PER_HOUR + int(minutes) * SECONDS_PER_MINUTE + int(secs)
    return whole + int(millis.ljust(MILLIS_DIGITS, "0")) / MILLIS_PER_SECOND


def _cue(block: str) -> Cue | None:
    timing = TIMING.search(block)
    if timing is None:
        return None
    body = block[timing.end() :]
    lines = tuple(
        stripped for raw in body.splitlines() if (stripped := MARKUP.sub("", raw).strip())
    )
    if not lines:
        return None
    return Cue(
        start=_seconds(*timing.group(1, 2, 3, 4)),
        end=_seconds(*timing.group(5, 6, 7, 8)),
        lines=lines,
    )
