from __future__ import annotations

import numpy as np
import pytest

from fmvcore import condition

RATE = 22050.0
ALL_ON = condition.Conditioning(remove_dc=True, compress=True, normalize=True, soft_clip=True)


def sine(
    frequency: float, seconds: float, *, rate: float = RATE, amplitude: float = 0.3
) -> np.ndarray:
    t = np.arange(int(seconds * rate), dtype=np.float64) / rate
    return amplitude * np.sin(2.0 * np.pi * frequency * t)


class TestTheSettings:
    def test_a_default_object_is_a_pass_through(self):
        # Arrange
        settings = condition.Conditioning()

        # Act
        enabled = settings.enabled

        # Assert
        assert enabled is False

    @pytest.mark.parametrize("field", ["remove_dc", "compress", "normalize", "soft_clip"])
    def test_any_stage_turns_it_on(self, field):
        # Arrange
        settings = condition.Conditioning(**{field: True})

        # Act
        enabled = settings.enabled

        # Assert
        assert enabled is True

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("dc_cutoff_hz", 0.0),
            ("ratio", 0.5),
            ("threshold", 0.0),
            ("threshold", 1.5),
            ("attack_s", 0.0),
            ("release_s", 0.0),
            ("peak_percentile", 0.0),
            ("peak_percentile", 2.0),
            ("peak_target", 0.0),
            ("peak_target", 1.5),
            ("silence_floor", -0.1),
            ("clip_knee", 1.0),
            ("clip_knee", -0.1),
        ],
    )
    def test_it_rejects_an_out_of_range_field(self, field, value):
        # Arrange
        kwargs = {field: value}

        # Act
        with pytest.raises(ValueError) as raised:
            condition.Conditioning(**kwargs)

        # Assert
        assert field.split("_")[0] in str(raised.value)


class TestConditionGuards:
    def test_it_rejects_a_rate_below_one(self):
        # Arrange
        signal = sine(440.0, 0.01)

        # Act
        with pytest.raises(ValueError) as raised:
            condition.condition(signal, rate_hz=0.5, settings=ALL_ON)

        # Assert
        assert "rate_hz" in str(raised.value)

    def test_it_rejects_a_non_mono_signal(self):
        # Arrange
        signal = np.zeros((4, 2), dtype=np.float64)

        # Act
        with pytest.raises(ValueError) as raised:
            condition.condition(signal, rate_hz=RATE, settings=ALL_ON)

        # Assert
        assert "mono" in str(raised.value)

    def test_an_empty_signal_stays_empty(self):
        # Arrange
        signal = np.zeros(0, dtype=np.float64)

        # Act
        out = condition.condition(signal, rate_hz=RATE, settings=ALL_ON)

        # Assert
        assert out.size == 0


class TestConditionBehaviour:
    def test_all_stages_off_is_a_pass_through(self):
        # Arrange
        signal = sine(440.0, 0.05)

        # Act
        out = condition.condition(signal, rate_hz=RATE, settings=condition.Conditioning())

        # Assert
        assert np.max(np.abs(out - signal)) < 1e-12

    def test_it_preserves_the_sample_count(self):
        # Arrange
        signal = sine(440.0, 0.1)

        # Act
        out = condition.condition(signal, rate_hz=RATE, settings=ALL_ON)

        # Assert
        assert out.shape == signal.shape

    def test_it_is_deterministic(self):
        # Arrange
        signal = sine(440.0, 0.1)

        # Act
        first = condition.condition(signal, rate_hz=RATE, settings=ALL_ON)

        # Assert
        assert np.array_equal(first, condition.condition(signal, rate_hz=RATE, settings=ALL_ON))

    def test_a_hot_source_stays_within_full_scale(self):
        # Arrange
        signal = sine(440.0, 0.1, amplitude=4.0)

        # Act
        out = condition.condition(signal, rate_hz=RATE, settings=ALL_ON)

        # Assert
        assert float(np.max(np.abs(out))) <= 1.0

    def test_digital_silence_stays_silent(self):
        # Arrange
        signal = np.zeros(2048, dtype=np.float64)

        # Act
        out = condition.condition(signal, rate_hz=RATE, settings=ALL_ON)

        # Assert
        assert float(np.max(np.abs(out))) == 0.0

    def test_normalize_lifts_a_quiet_source(self):
        # Arrange
        signal = sine(440.0, 0.2, amplitude=0.05)

        # Act
        out = condition.condition(
            signal, rate_hz=RATE, settings=condition.Conditioning(normalize=True)
        )

        # Assert
        assert float(np.max(np.abs(out))) > float(np.max(np.abs(signal)))

    def test_normalize_leaves_near_silence_alone(self):
        # Arrange
        signal = np.full(2048, 1e-5, dtype=np.float64)

        # Act
        out = condition.condition(
            signal,
            rate_hz=RATE,
            settings=condition.Conditioning(normalize=True, silence_floor=1e-3),
        )

        # Assert
        assert np.max(np.abs(out - signal)) < 1e-12

    def test_remove_dc_strips_a_constant_offset(self):
        # Arrange
        signal = sine(440.0, 0.5) + 0.4

        # Act
        out = condition.condition(
            signal, rate_hz=RATE, settings=condition.Conditioning(remove_dc=True)
        )

        # Assert
        assert abs(float(np.mean(out[-1024:]))) < abs(float(np.mean(signal)))

    def test_compress_reduces_the_crest_of_a_loud_source(self):
        # Arrange
        signal = sine(440.0, 0.5, amplitude=0.9)

        # Act
        out = condition.condition(
            signal, rate_hz=RATE, settings=condition.Conditioning(compress=True)
        )

        # Assert
        assert float(np.max(np.abs(out[-1024:]))) < float(np.max(np.abs(signal)))

    def test_soft_clip_leaves_low_levels_untouched(self):
        # Arrange
        signal = sine(440.0, 0.05, amplitude=0.5)

        # Act
        out = condition.condition(
            signal, rate_hz=RATE, settings=condition.Conditioning(soft_clip=True)
        )

        # Assert
        assert np.max(np.abs(out - signal)) < 1e-12

    def test_soft_clip_saturates_a_peak_below_full_scale(self):
        # Arrange
        signal = np.full(16, 0.99, dtype=np.float64)

        # Act
        out = condition.condition(
            signal, rate_hz=RATE, settings=condition.Conditioning(soft_clip=True)
        )

        # Assert
        assert float(out[0]) < 0.99


class TestConditionInt16:
    def test_off_returns_the_samples_unchanged(self):
        # Arrange
        samples = (sine(440.0, 0.1) * condition.FULL_SCALE).astype(np.int16)

        # Act
        out = condition.condition_int16(samples, rate_hz=RATE, settings=condition.Conditioning())

        # Assert
        assert np.array_equal(out, samples)

    def test_empty_returns_empty_int16(self):
        # Arrange
        samples = np.zeros(0, dtype=np.int16)

        # Act
        out = condition.condition_int16(samples, rate_hz=RATE, settings=ALL_ON)

        # Assert
        assert out.dtype == np.int16 and out.size == 0

    def test_on_preserves_length_and_dtype(self):
        # Arrange
        samples = (sine(440.0, 0.1, amplitude=0.05) * condition.FULL_SCALE).astype(np.int16)

        # Act
        out = condition.condition_int16(
            samples, rate_hz=RATE, settings=condition.Conditioning(normalize=True)
        )

        # Assert
        assert out.dtype == np.int16 and out.shape == samples.shape

    def test_on_never_wraps(self):
        # Arrange
        samples = np.full(256, condition.INT16_MAX, dtype=np.int16)

        # Act
        out = condition.condition_int16(samples, rate_hz=RATE, settings=ALL_ON)

        # Assert
        assert int(out.min()) >= condition.INT16_MIN and int(out.max()) <= condition.INT16_MAX
