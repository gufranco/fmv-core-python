from __future__ import annotations

import numpy as np

from fmvcore import capture

HEIGHT = 24
WIDTH = 32


def flat(level: int) -> np.ndarray:
    return np.full((HEIGHT, WIDTH, 3), level, dtype=np.uint8)


def gradient(shift: int) -> np.ndarray:
    columns = np.arange(WIDTH, dtype=np.int32)[None, :, None]
    rows = np.arange(HEIGHT, dtype=np.int32)[:, None, None]
    return ((columns * 3 + rows + shift * 40) % 256).astype(np.uint8).repeat(3, axis=2)


def film(count: int) -> np.ndarray:
    return np.stack([gradient(shift) for shift in range(count)])


class TestAlignment:
    def test_a_capture_that_matches_from_an_offset_is_found(self):
        # Arrange
        fields = film(12)
        recorded = np.concatenate([np.zeros((3, HEIGHT, WIDTH, 3), dtype=np.uint8), fields])

        # Act
        found = capture.align(recorded, fields)

        # Assert
        assert found == capture.Alignment(offset=3, mismatches=0, sampled=11)

    def test_a_capture_that_never_matches_reports_every_sample(self):
        # Arrange
        fields = film(12)
        recorded = np.full_like(fields, 7)

        # Act
        found = capture.align(recorded, fields)

        # Assert
        assert found.mismatches == found.sampled

    def test_a_capture_shorter_than_the_stream_stops_the_search(self):
        # Arrange
        fields = film(12)
        recorded = fields[:2]

        # Act
        found = capture.align(recorded, fields)

        # Assert
        assert found.mismatches == found.sampled


class TestMixing:
    def test_a_clean_transfer_mixes_nothing(self):
        # Arrange
        before, after = flat(10), flat(200)
        fields = np.stack([before, before, after])

        # Act
        share = capture.mixed_share(fields, completes=[0, 2])

        # Assert
        assert share == 0.0

    def test_a_field_matching_neither_frame_is_counted(self):
        # Arrange
        fields = np.stack([flat(10), flat(90), flat(200)])

        # Act
        share = capture.mixed_share(fields, completes=[0, 2])

        # Assert
        assert share == 1.0

    def test_frames_with_no_field_between_them_mix_nothing(self):
        # Arrange
        fields = np.stack([flat(10), flat(200)])

        # Act
        share = capture.mixed_share(fields, completes=[0, 1])

        # Assert
        assert share == 0.0


class TestLag:
    def test_a_frame_shown_on_time_has_no_lag(self):
        # Arrange
        source = film(10)
        shown = source.copy()

        # Act
        lags = capture.measured_lags(shown, source, completes=[2, 5, 8], window=4)

        # Assert
        assert lags == [0, 0, 0]

    def test_a_frame_shown_late_reports_how_late(self):
        # Arrange
        source = film(10)
        shown = np.roll(source, 2, axis=0)

        # Act
        lags = capture.measured_lags(shown, source, completes=[4, 6, 8], window=4)

        # Assert
        assert lags == [2, 2, 2]

    def test_a_completion_past_the_capture_is_not_measured(self):
        # Arrange
        source = film(6)

        # Act
        lags = capture.measured_lags(source, source, completes=[2, 9], window=2)

        # Assert
        assert lags == [0]
