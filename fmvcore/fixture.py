from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

WIDTH: Final = 256
HEIGHT: Final = 192
FRAMES: Final = 24
RATE: Final = 12
SEED: Final = 20260906
QUALITY: Final = 10
BLOCK: Final = 32
BAR_WIDTH: Final = 24
BAR_SPEED: Final = 6
BAR_LIFT: Final = 66
LEVEL_LOW: Final = 3
LEVEL_HIGH: Final = 12
LEVEL_STEP: Final = 18

FIXTURE: Final = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic.mp4"

Grid = tuple[npt.NDArray[np.intp], npt.NDArray[np.intp]]


def frame_at(index: int, base: npt.NDArray[np.int16], grid: Grid) -> npt.NDArray[np.uint8]:
    columns, rows = grid
    ramp = ((columns % 8) * 6 + (rows % 8) * 4 - 34)[..., None]
    sweep = (36 * np.sin((columns + 11 * index) / 23.0))[..., None]
    bar = (((columns + BAR_SPEED * index) % WIDTH) < BAR_WIDTH)[..., None] * BAR_LIFT
    clipped: npt.NDArray[np.float64] = np.clip(base + ramp + sweep + bar, 0, 255)
    return clipped.astype(np.uint8)


def encoder_command(target: Path) -> tuple[str, ...]:
    return (
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}", "-r", str(RATE), "-i", "-",
        "-c:v", "libx264", "-crf", str(QUALITY), "-preset", "veryslow",
        "-pix_fmt", "yuv420p", str(target),
    )  # fmt: skip


def block_field() -> tuple[npt.NDArray[np.int16], Grid]:
    columns, rows = np.meshgrid(np.arange(WIDTH), np.arange(HEIGHT))
    rng = np.random.default_rng(SEED)
    levels = rng.integers(
        LEVEL_LOW, LEVEL_HIGH, size=(HEIGHT // BLOCK, WIDTH // BLOCK, 3), dtype=np.uint8
    )
    blocks = levels * LEVEL_STEP
    base = np.kron(blocks, np.ones((BLOCK, BLOCK, 1), dtype=np.uint8)).astype(np.int16)
    return base, (columns, rows)


def build(target: Path = FIXTURE, *, command: Sequence[str] | None = None) -> Path:
    base, grid = block_field()
    target.parent.mkdir(parents=True, exist_ok=True)
    chosen = tuple(command) if command is not None else encoder_command(target)
    pictures = b"".join(frame_at(index, base, grid).tobytes() for index in range(FRAMES))
    done = subprocess.run(chosen, input=pictures, check=False)
    if done.returncode != 0:
        msg = f"ffmpeg exited {done.returncode}"
        raise RuntimeError(msg)
    return target


def main(argv: Sequence[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    written = build(Path(arguments[0]) if arguments else FIXTURE)
    print(f"wrote {written} ({written.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
