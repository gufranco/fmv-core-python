from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt

RGB_CHANNELS: Final = 3
BYTE_MAX: Final = 255.0
SRGB_LINEAR_LIMIT: Final = 0.04045
BLUR_TAPS: Final = (1.0, 4.0, 6.0, 4.0, 1.0)
FRAMES_NDIM: Final = 4
TO_CONES: Final = np.array(
    [
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ]
)
TO_OKLAB: Final = np.array(
    [
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ]
)

Frames = npt.NDArray[np.uint8]


def srgb_to_oklab(rgb: npt.NDArray[np.floating]) -> npt.NDArray[np.float32]:
    if rgb.shape[-1] != RGB_CHANNELS:
        msg = f"expected a trailing RGB axis, got shape {rgb.shape}"
        raise ValueError(msg)
    value = np.asarray(rgb, dtype=np.float64)
    linear = np.where(
        value <= SRGB_LINEAR_LIMIT,
        value / 12.92,
        np.power((value + 0.055) / 1.055, 2.4),
    )

    cones: npt.NDArray[np.float64] = linear @ TO_CONES.T
    lab: npt.NDArray[np.float64] = np.cbrt(cones) @ TO_OKLAB.T
    return lab.astype(np.float32)


def oklab_error(shown: Frames, wanted: Frames) -> float:
    a = _oklab(shown)
    b = _oklab(wanted)
    return float(np.sqrt(((a - b) ** 2).sum(-1)).mean())


def blurred_error(shown: Frames, wanted: Frames) -> float:
    if shown.shape != wanted.shape or shown.ndim != FRAMES_NDIM:
        msg = f"cannot compare frames shaped {shown.shape} and {wanted.shape}"
        raise ValueError(msg)
    a = _blurred(_oklab(shown))
    b = _blurred(_oklab(wanted))
    return float(np.sqrt(((a - b) ** 2).sum(-1)).mean())


def _oklab(frames: Frames) -> npt.NDArray[np.float32]:
    return srgb_to_oklab(frames.astype(np.float32) / BYTE_MAX)


def _blurred(lab: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
    taps = np.array(BLUR_TAPS, dtype=np.float32) / sum(BLUR_TAPS)
    reach = len(BLUR_TAPS) // 2
    height, width = lab.shape[1], lab.shape[2]
    padded = np.pad(lab, ((0, 0), (reach, reach), (reach, reach), (0, 0)), mode="edge")
    rows = sum(tap * padded[:, i : i + height] for i, tap in enumerate(taps))
    return np.asarray(sum(tap * rows[:, :, i : i + width] for i, tap in enumerate(taps)))
