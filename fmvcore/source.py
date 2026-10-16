from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fmvcore import ffmpeg

CROP: Final = re.compile(r"crop=(\d+):(\d+):(\d+):(\d+)")
MULTI_FIELDS: Final = re.compile(r"(TFF|BFF|Progressive|Undetermined):(\d+)")
MULTI_FRAME: Final = "Multi frame detection"
CROP_FILTER: Final = "cropdetect=limit=24:round=2"
INTERLACE_FILTER: Final = "idet"

Bars = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class SourceAnalysis:
    interlaced: bool
    crop: Bars | None


def analyse(path: Path, *, start: float = 0.0, duration: float = 8.0) -> SourceAnalysis:
    verdict = _run_filter(path, INTERLACE_FILTER, start=start, duration=duration)
    bars = _run_filter(path, CROP_FILTER, start=start, duration=duration)
    return SourceAnalysis(interlaced=_interlaced(verdict), crop=_crop(path, bars))


def _interlaced(verdict: str) -> bool:
    summaries = [line for line in verdict.splitlines() if MULTI_FRAME in line]
    if not summaries:
        return False
    fields = dict(MULTI_FIELDS.findall(summaries[-1].replace(" ", "")))
    woven = int(fields.get("TFF", 0)) + int(fields.get("BFF", 0))
    return woven > int(fields.get("Progressive", 0))


def _crop(path: Path, report: str) -> Bars | None:
    matches = CROP.findall(report)
    if not matches:
        return None
    width, height, left, top = (int(value) for value in matches[-1])
    info = ffmpeg.probe(path)
    if width < info.width or height < info.height:
        return (width, height, left, top)
    return None


def _run_filter(path: Path, filter_spec: str, *, start: float, duration: float) -> str:
    command = [
        ffmpeg.require_tool("ffmpeg"),
        "-hide_banner",
        "-ss",
        f"{start:.6f}",
        "-i",
        str(path),
        "-t",
        f"{duration:.6f}",
        "-vf",
        filter_spec,
        "-an",
        "-f",
        "null",
        "-",
    ]
    return subprocess.run(command, capture_output=True, check=True, text=True).stderr
