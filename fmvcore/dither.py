from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt

NO_DITHER: Final = 0.0
MAX_DITHER: Final = 1.0
MIX_SCALE: Final = 255.0
BAYER_SIDE: Final = 8
FEWEST_TO_MIX: Final = 2
_BAYER_8: Final = np.array(
    [
        [0, 32, 8, 40, 2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44, 4, 36, 14, 46, 6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [3, 35, 11, 43, 1, 33, 9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47, 7, 39, 13, 45, 5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21],
    ],
    dtype=np.float32,
)

Picks = npt.NDArray[np.uint8]


def check_strength(strength: float) -> None:
    if not NO_DITHER <= strength <= MAX_DITHER:
        msg = f"a dither strength lies between {NO_DITHER:g} and {MAX_DITHER:g}, got {strength:g}"
        raise ValueError(msg)


def bayer_thresholds(side: int) -> npt.NDArray[np.float32]:
    if side <= 0 or side % BAYER_SIDE:
        msg = f"a threshold field is whole multiples of {BAYER_SIDE} pixels, got {side}"
        raise ValueError(msg)
    unit = (_BAYER_8 + 0.5) / float(BAYER_SIDE * BAYER_SIDE)
    repeat = side // BAYER_SIDE
    return np.tile(unit, (repeat, repeat)).astype(np.float32)


def two_nearest(distance: npt.NDArray[np.floating], strength: float) -> tuple[Picks, Picks, Picks]:
    check_strength(strength)
    nearest = np.argmin(distance, axis=-1)
    near_squared = np.take_along_axis(distance, nearest[..., None], axis=-1)[..., 0]
    if distance.shape[-1] < FEWEST_TO_MIX:
        zero = np.zeros(nearest.shape, dtype=np.uint8)
        return nearest.astype(np.uint8), nearest.astype(np.uint8), zero
    others = distance.copy()
    np.put_along_axis(others, nearest[..., None], np.inf, axis=-1)
    runner = np.argmin(others, axis=-1)
    near = np.sqrt(near_squared)
    far = np.sqrt(np.take_along_axis(others, runner[..., None], axis=-1)[..., 0])
    total = near + far
    share = np.divide(near, total, out=np.zeros_like(near), where=total > 0.0)
    return (
        nearest.astype(np.uint8),
        runner.astype(np.uint8),
        np.rint(share * MIX_SCALE * strength).astype(np.uint8),
    )


def mix(nearest: Picks, runner: Picks, share: Picks, threshold: npt.NDArray[np.float32]) -> Picks:
    return np.where(share > threshold * MIX_SCALE, runner, nearest).astype(np.uint8)
