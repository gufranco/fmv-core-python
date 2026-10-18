from __future__ import annotations

import numpy as np
import pytest

from fmvcore import colour

OKLAB_MIDPOINT_GREY = 100
HALF_LIGHT_GREY = 188
GREY_40_TO_200_OKLAB = 0.5559456
SIDE = 16


def flat(level: int, *, frames: int = 1) -> np.ndarray:
    return np.full((frames, SIDE, SIDE, 3), level, dtype=np.uint8)


def against_grey(pattern: np.ndarray, grey: int = HALF_LIGHT_GREY) -> tuple[np.ndarray, np.ndarray]:
    lit = np.where(pattern[..., None] == 0, 255, 0).astype(np.uint8)
    shown = np.broadcast_to(lit, (1, SIDE, SIDE, 3)).copy()
    return shown, flat(grey)


class TestSrgbToOklab:
    def test_black_sits_at_the_origin(self):
        # Arrange
        rgb = np.zeros((1, 3), dtype=np.float32)

        # Act
        result = colour.srgb_to_oklab(rgb)

        # Assert
        assert result[0, 0] == pytest.approx(0.0, abs=1e-6)

    def test_white_has_unit_lightness_and_no_chroma(self):
        # Arrange
        rgb = np.ones((1, 3), dtype=np.float32)

        # Act
        result = colour.srgb_to_oklab(rgb)

        # Assert
        assert result[0].tolist() == pytest.approx([1.0, 0.0, 0.0], abs=1e-3)

    def test_an_array_without_an_rgb_axis_is_refused(self):
        # Arrange
        rgb = np.zeros((4, 2), dtype=np.float32)

        # Act
        with pytest.raises(ValueError) as refused:
            colour.srgb_to_oklab(rgb)

        # Assert
        assert str(refused.value) == "expected a trailing RGB axis, got shape (4, 2)"


class TestOklabError:
    def test_identical_pictures_have_no_error(self):
        # Arrange
        shown, wanted = flat(120), flat(120)

        # Act
        error = colour.oklab_error(shown, wanted)

        # Assert
        assert error == 0.0

    def test_black_against_white_is_a_whole_unit_of_lightness(self):
        # Arrange
        shown, wanted = flat(0), flat(255)

        # Act
        error = colour.oklab_error(shown, wanted)

        # Assert
        assert error == pytest.approx(1.0, abs=1e-3)


class TestBlurredError:
    def test_identical_frames_have_no_blurred_error(self):
        # Arrange
        frames = np.random.default_rng(7).integers(0, 256, (2, SIDE, SIDE, 3), dtype=np.uint8)

        # Act
        error = colour.blurred_error(frames, frames.copy())

        # Assert
        assert error == 0.0

    def test_flat_frames_score_the_same_blurred_or_not(self):
        # Arrange
        shown, wanted = flat(40), flat(200)

        # Act
        error = colour.blurred_error(shown, wanted)

        # Assert
        assert error == pytest.approx(GREY_40_TO_200_OKLAB, rel=1e-4)

    def test_a_fine_checker_matches_the_grey_giving_half_its_light_once_blurred(self):
        # Arrange
        rows, columns = np.mgrid[0:SIDE, 0:SIDE]
        shown, wanted = against_grey((rows + columns) % 2)

        # Act
        error = colour.blurred_error(shown, wanted)

        # Assert
        assert error < colour.oklab_error(shown, wanted) / 20

    def test_vertical_stripes_match_the_grey_at_their_midpoint_once_blurred(self):
        # Arrange
        _, columns = np.mgrid[0:SIDE, 0:SIDE]
        shown, wanted = against_grey(columns % 2)

        # Act
        error = colour.blurred_error(shown, wanted)

        # Assert
        assert error < colour.oklab_error(shown, wanted) / 4

    def test_horizontal_stripes_match_the_grey_at_their_midpoint_once_blurred(self):
        # Arrange
        rows, _ = np.mgrid[0:SIDE, 0:SIDE]
        shown, wanted = against_grey(rows % 2)

        # Act
        error = colour.blurred_error(shown, wanted)

        # Assert
        assert error < colour.oklab_error(shown, wanted) / 4

    def test_a_checker_is_closer_to_half_its_light_than_to_its_oklab_midpoint(self):
        # Arrange
        rows, columns = np.mgrid[0:SIDE, 0:SIDE]
        checker = (rows + columns) % 2
        shown, darker = against_grey(checker, OKLAB_MIDPOINT_GREY)
        lighter = flat(HALF_LIGHT_GREY)

        # Act
        errors = (colour.blurred_error(shown, lighter), colour.blurred_error(shown, darker))

        # Assert
        assert errors[0] < errors[1] / 10


class TestBlurredErrorRefusals:
    def test_frames_of_different_shapes_are_refused(self):
        # Arrange
        shown, wanted = flat(0), flat(0, frames=2)

        # Act
        with pytest.raises(ValueError) as refused:
            colour.blurred_error(shown, wanted)

        # Assert
        assert (
            str(refused.value) == "cannot compare frames shaped (1, 16, 16, 3) and (2, 16, 16, 3)"
        )

    def test_a_single_frame_without_a_batch_axis_is_refused(self):
        # Arrange
        frame = np.zeros((SIDE, SIDE, 3), dtype=np.uint8)

        # Act
        with pytest.raises(ValueError) as refused:
            colour.blurred_error(frame, frame)

        # Assert
        assert str(refused.value) == "cannot compare frames shaped (16, 16, 3) and (16, 16, 3)"
