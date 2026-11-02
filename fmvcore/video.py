from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

from fmvcore import ffmpeg

LOSSLESS_SUFFIXES: Final = frozenset({".mkv"})
MOST_ENLARGEMENT: Final = 8
MACROBLOCK: Final = 16
LEVEL_FRAME_BLOCKS: Final = 36_864
LEVEL_BLOCK_RATE: Final = 983_040
HIGHEST_LEVEL: Final = 51
MOST_DRIFT: Final = 5
RGB: Final = 3
EXPECTED_STREAM: Final = {
    "codec_name": "h264",
    "profile": "High",
    "pix_fmt": "yuv420p",
    "color_space": "bt709",
    "color_range": "tv",
}
NEAR_LOSSLESS: Final = (
    "-c:v",
    "libx264",
    "-profile:v",
    "high",
    "-preset",
    "slow",
    "-qp",
    "1",
    "-x264-params",
    "no-deblock=1:psy-rd=0,0:aq-mode=0",
    "-colorspace",
    "bt709",
    "-color_primaries",
    "bt709",
    "-color_trc",
    "bt709",
    "-color_range",
    "tv",
    "-movflags",
    "+faststart",
    "-an",
)
LOSSLESS: Final = ("-c:v", "ffv1", "-level", "3", "-pix_fmt", "rgb24", "-an")
DECODE_BACK: Final = (
    "scale=in_color_matrix=bt709:in_range=tv:flags=neighbor+accurate_rnd,format=rgb24"
)


@dataclass(frozen=True, slots=True)
class Picture:
    width: int
    height: int
    rate: Fraction


def enlargement(picture: Picture) -> int:
    for factor in range(MOST_ENLARGEMENT, 0, -1):
        across = math.ceil(picture.width * factor / MACROBLOCK)
        down = math.ceil(picture.height * factor / MACROBLOCK)
        blocks = across * down
        if blocks <= LEVEL_FRAME_BLOCKS and blocks * picture.rate <= LEVEL_BLOCK_RATE:
            return factor
    msg = f"a {picture.width}x{picture.height} picture does not fit H.264 level 5.1 at 1x"
    raise ValueError(msg)


def is_lossless(path: Path) -> bool:
    return path.suffix.lower() in LOSSLESS_SUFFIXES


def writer_command(path: Path, picture: Picture) -> list[str]:
    reader = [
        ffmpeg.require_tool("ffmpeg"),
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{picture.width}x{picture.height}",
        "-framerate",
        f"{picture.rate.numerator}/{picture.rate.denominator}",
        "-i",
        "-",
    ]
    return [*reader, *_encoding(path, picture), str(path)]


def _encoding(path: Path, picture: Picture) -> list[str]:
    if is_lossless(path):
        return list(LOSSLESS)
    factor = enlargement(picture)
    enlarge = (
        f"scale=iw*{factor}:ih*{factor}:out_color_matrix=bt709:out_range=tv:"
        "flags=neighbor+accurate_rnd,format=yuv420p"
    )
    return ["-vf", enlarge, *NEAR_LOSSLESS]


def check(path: Path, picture: Picture, frames: Sequence[npt.NDArray[np.uint8]]) -> None:
    if is_lossless(path):
        return
    _check_stream(_stream(path))
    factor = enlargement(picture)
    decoded = _decoded(path, picture, factor, len(frames))
    drift = max(
        int(np.abs(shown.astype(np.int16) - wanted.astype(np.int16)).max())
        for shown, wanted in zip(decoded, frames, strict=True)
    )
    if drift > MOST_DRIFT:
        msg = f"{path} drifts {drift} levels from the console picture, past {MOST_DRIFT}"
        raise ValueError(msg)


def _stream(path: Path) -> dict[str, object]:
    command = [
        ffmpeg.require_tool("ffprobe"),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,profile,pix_fmt,level,color_space,color_range",
        "-of",
        "json",
        str(path),
    ]
    done = subprocess.run(command, capture_output=True, text=True, check=True)
    streams = json.loads(done.stdout).get("streams") or [{}]
    return dict(streams[0])


def _check_stream(stream: dict[str, object]) -> None:
    wrong = {
        key: stream.get(key) for key, value in EXPECTED_STREAM.items() if stream.get(key) != value
    }
    level = stream.get("level")
    if not isinstance(level, int) or level > HIGHEST_LEVEL:
        wrong = {**wrong, "level": level}
    if wrong:
        msg = f"the preview is not the near-lossless H.264 every player opens: {wrong}"
        raise ValueError(msg)


def _decoded(path: Path, picture: Picture, factor: int, count: int) -> list[npt.NDArray[np.uint8]]:
    command = [
        ffmpeg.require_tool("ffmpeg"),
        "-v",
        "error",
        "-i",
        str(path),
        "-vf",
        DECODE_BACK,
        "-frames:v",
        str(count),
        "-f",
        "rawvideo",
        "-",
    ]
    raw = subprocess.run(command, capture_output=True, check=True).stdout
    shape = (-1, picture.height * factor, picture.width * factor, RGB)
    big = np.frombuffer(raw, np.uint8).reshape(shape)
    middle = factor // 2
    return list(big[:, middle::factor, middle::factor])
