from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

FULL_SCALE: Final = 32767.0
INT16_MIN: Final = -32768
INT16_MAX: Final = 32767
MIN_RATE_HZ: Final = 1.0
UNIT: Final = 1.0


@dataclass(frozen=True, slots=True)
class Conditioning:
    remove_dc: bool = False
    compress: bool = False
    normalize: bool = False
    soft_clip: bool = False
    dc_cutoff_hz: float = 20.0
    threshold: float = 0.125
    ratio: float = 3.0
    attack_s: float = 0.005
    release_s: float = 0.150
    peak_percentile: float = 0.999
    peak_target: float = 0.9
    silence_floor: float = 1e-4
    clip_knee: float = 0.8

    def __post_init__(self) -> None:
        if not 0.0 < self.dc_cutoff_hz < FULL_SCALE:
            raise ValueError(f"dc_cutoff_hz must be positive and audible, got {self.dc_cutoff_hz}")
        if self.ratio < UNIT:
            raise ValueError(f"a compressor ratio is at least 1, got {self.ratio}")
        if not 0.0 < self.threshold <= UNIT:
            raise ValueError(f"threshold lies in (0, 1], got {self.threshold}")
        if self.attack_s <= 0.0 or self.release_s <= 0.0:
            raise ValueError(
                f"attack and release are positive, got {self.attack_s}, {self.release_s}"
            )
        if not 0.0 < self.peak_percentile <= UNIT:
            raise ValueError(f"peak_percentile lies in (0, 1], got {self.peak_percentile}")
        if not 0.0 < self.peak_target <= UNIT:
            raise ValueError(f"peak_target lies in (0, 1], got {self.peak_target}")
        if self.silence_floor < 0.0:
            raise ValueError(f"silence_floor is not negative, got {self.silence_floor}")
        if not 0.0 <= self.clip_knee < UNIT:
            raise ValueError(f"clip_knee lies in [0, 1), got {self.clip_knee}")

    @property
    def enabled(self) -> bool:
        return self.remove_dc or self.compress or self.normalize or self.soft_clip


def condition(
    signal: npt.NDArray[np.floating], *, rate_hz: float, settings: Conditioning
) -> npt.NDArray[np.float64]:
    if rate_hz < MIN_RATE_HZ:
        raise ValueError(f"rate_hz is at least {MIN_RATE_HZ}, got {rate_hz}")
    out = np.asarray(signal, dtype=np.float64).copy()
    if out.ndim != 1:
        raise ValueError(f"signal must be mono, got shape {out.shape}")
    if out.size == 0:
        return out
    if settings.remove_dc:
        out = _remove_dc(out, rate_hz=rate_hz, cutoff_hz=settings.dc_cutoff_hz)
    if settings.compress:
        out = _compress(out, rate_hz=rate_hz, settings=settings)
    if settings.normalize:
        out = _normalize(out, settings=settings)
    if settings.soft_clip:
        out = _soft_clip(out, knee=settings.clip_knee)
    return np.clip(out, -UNIT, UNIT)


def condition_int16(
    samples: npt.NDArray[np.integer], *, rate_hz: float, settings: Conditioning
) -> npt.NDArray[np.int16]:
    if samples.size == 0 or not settings.enabled:
        return np.asarray(samples, dtype=np.int16)
    floats = np.asarray(samples, dtype=np.float64) / FULL_SCALE
    shaped = condition(floats, rate_hz=rate_hz, settings=settings)
    scaled = np.rint(shaped * FULL_SCALE)
    return np.clip(scaled, INT16_MIN, INT16_MAX).astype(np.int16)


def _remove_dc(
    signal: npt.NDArray[np.float64], *, rate_hz: float, cutoff_hz: float
) -> npt.NDArray[np.float64]:
    pole = 1.0 - 2.0 * math.pi * cutoff_hz / rate_hz
    out = np.empty_like(signal)
    dc = 0.0
    for i, value in enumerate(signal):
        dc = pole * dc + (1.0 - pole) * value
        out[i] = value - dc
    return out


def _compress(
    signal: npt.NDArray[np.float64], *, rate_hz: float, settings: Conditioning
) -> npt.NDArray[np.float64]:
    attack = math.exp(-1.0 / (settings.attack_s * rate_hz))
    release = math.exp(-1.0 / (settings.release_s * rate_hz))
    exponent = 1.0 / settings.ratio - 1.0
    out = signal.copy()
    env = 0.0
    for i, value in enumerate(signal):
        magnitude = abs(value)
        coeff = attack if magnitude > env else release
        env = coeff * env + (1.0 - coeff) * magnitude
        if env > settings.threshold:
            out[i] = value * (env / settings.threshold) ** exponent
    return out


def _normalize(
    signal: npt.NDArray[np.float64], *, settings: Conditioning
) -> npt.NDArray[np.float64]:
    peak = float(np.quantile(np.abs(signal), settings.peak_percentile))
    if peak < settings.silence_floor:
        return signal
    return signal * (settings.peak_target / peak)


def _soft_clip(signal: npt.NDArray[np.float64], *, knee: float) -> npt.NDArray[np.float64]:
    magnitude = np.abs(signal)
    headroom = UNIT - knee
    excess = np.maximum(magnitude - knee, 0.0)
    shaped = knee + headroom * np.tanh(excess / headroom)
    return np.where(magnitude <= knee, signal, np.sign(signal) * shaped)
