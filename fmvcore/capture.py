from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Final

import numpy as np
import numpy.typing as npt

ALIGN_SAMPLES: Final = 48
ALIGN_SEARCH: Final = 64
THUMB: Final = 8

Frames = npt.NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class Played:
    fields: Frames
    completes: list[int]


@dataclass(frozen=True, slots=True)
class Alignment:
    offset: int
    mismatches: int
    sampled: int


def align(recorded: Frames, fields: Frames) -> Alignment:
    last = max(fields.shape[0] - 2, 0)
    sampled = np.linspace(0, last, min(ALIGN_SAMPLES, last + 1)).astype(int)
    best = Alignment(offset=0, mismatches=len(sampled), sampled=len(sampled))
    for offset in range(min(ALIGN_SEARCH, recorded.shape[0])):
        usable = [i for i in sampled if i + offset < recorded.shape[0]]
        if len(usable) < len(sampled):
            break
        bad = sum(int(not np.array_equal(recorded[i + offset], fields[i])) for i in usable)
        if bad < best.mismatches:
            best = Alignment(offset=offset, mismatches=bad, sampled=len(sampled))
    return best


def mixed_share(fields: Frames, *, completes: list[int]) -> float:
    shares: list[float] = []
    for previous, current in pairwise(completes):
        for index in range(previous + 1, current):
            shown = fields[index]
            neither = np.any(shown != fields[previous], -1) & np.any(shown != fields[current], -1)
            shares.append(float(neither.mean()))
    return float(np.mean(shares)) if shares else 0.0


def measured_lags(shown: Frames, source: Frames, *, completes: list[int], window: int) -> list[int]:
    small_source = _thumbnails(source)
    lags: list[int] = []
    for field in completes:
        if field >= shown.shape[0]:
            break
        here = _thumbnails(shown[field : field + 1])[0]
        low = max(0, field - window)
        high = min(small_source.shape[0], field + window + 1)
        distances = np.abs(small_source[low:high] - here).mean(axis=(1, 2, 3))
        lags.append(field - (low + int(np.argmin(distances))))
    return lags


def _thumbnails(frames: Frames) -> npt.NDArray[np.float32]:
    count, height, width, _ = frames.shape
    trimmed = frames[:, : height - height % THUMB, : width - width % THUMB].astype(np.float32)
    return trimmed.reshape(count, height // THUMB, THUMB, width // THUMB, THUMB, 3).mean(
        axis=(2, 4)
    )
