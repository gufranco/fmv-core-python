from __future__ import annotations

import numpy as np
import pytest

from fmvcore import dither

SMS_TILE = 8
NEOGEO_TILE = 16


PAIR_SPACING = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)


def ramp_distance(pixels: int) -> np.ndarray:
    position = np.linspace(0.0, 1.0, pixels, dtype=np.float32)
    entries = np.array([0.0, 1.0], dtype=np.float32)
    return (position[:, None] - entries[None, :]) ** 2


def spacing_of(points: np.ndarray) -> np.ndarray:
    return ((points[:, None, :] - points[None, :, :]) ** 2).sum(axis=-1)


class TestTheThresholdField:
    @pytest.mark.parametrize("side", [SMS_TILE, NEOGEO_TILE], ids=["8x8", "16x16"])
    def test_it_covers_a_whole_tile(self, side):
        # Arrange
        expected = (side, side)

        # Act
        field = dither.bayer_thresholds(side)

        # Assert
        assert field.shape == expected

    def test_it_stays_inside_the_unit_interval(self):
        # Arrange
        side = NEOGEO_TILE

        # Act
        field = dither.bayer_thresholds(side)

        # Assert
        assert (float(field.min()), float(field.max())) == (0.5 / 64, 63.5 / 64)

    def test_it_repeats_every_eight_pixels(self):
        # Arrange
        period = dither.BAYER_SIDE

        # Act
        field = dither.bayer_thresholds(NEOGEO_TILE)

        # Assert
        assert np.array_equal(field[:period, :period], field[period:, period:])
        assert np.array_equal(field[:period, :period], field[period:, :period])

    def test_every_level_appears_once_in_an_eight_pixel_tile(self):
        # Arrange
        side = SMS_TILE

        # Act
        field = dither.bayer_thresholds(side)

        # Assert
        assert np.unique(field).size == side * side

    @pytest.mark.parametrize("side", [0, 4, 12], ids=["empty", "short", "ragged"])
    def test_a_side_that_is_not_whole_periods_is_refused(self, side):
        # Arrange
        expected = f"a threshold field is whole multiples of 8 pixels, got {side}"

        # Act
        with pytest.raises(ValueError) as refused:
            dither.bayer_thresholds(side)

        # Assert
        assert str(refused.value) == expected


class TestTwoNearest:
    def test_a_tie_takes_the_first_entry_as_the_undithered_choice_does(self):
        # Arrange
        rng = np.random.default_rng(7)
        base = rng.random((4096, 8), dtype=np.float32)
        distance = np.concatenate([base, base], axis=1)[:, rng.permutation(16)]
        spacing = np.ones((16, 16), dtype=np.float32)

        # Act
        nearest, _, _ = dither.two_nearest(distance, spacing, dither.MAX_DITHER)

        # Assert
        assert np.array_equal(nearest, np.argmin(distance, axis=1))

    def test_the_runner_up_is_never_the_nearest(self):
        # Arrange
        distance = np.array([[1.0, 1.0, 5.0], [3.0, 1.0, 1.0]], dtype=np.float32)
        spacing = np.ones((3, 3), dtype=np.float32)

        # Act
        nearest, runner, _ = dither.two_nearest(distance, spacing, dither.MAX_DITHER)

        # Assert
        assert (nearest.tolist(), runner.tolist()) == ([0, 1], [1, 2])

    def test_a_point_midway_shares_half(self):
        # Arrange
        distance = np.array([[0.25, 0.25]], dtype=np.float32)

        # Act
        _, _, share = dither.two_nearest(distance, PAIR_SPACING, dither.MAX_DITHER)

        # Assert
        assert share.tolist() == [128]

    def test_a_point_on_an_entry_shares_nothing(self):
        # Arrange
        distance = np.array([[0.0, 1.0]], dtype=np.float32)

        # Act
        _, _, share = dither.two_nearest(distance, PAIR_SPACING, dither.MAX_DITHER)

        # Assert
        assert share.tolist() == [0]

    def test_a_colour_beyond_both_entries_is_never_mixed(self):
        # Arrange
        entries = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 3.0]], dtype=np.float32)
        pixel = np.array([[-0.5, 0.0]], dtype=np.float32)
        distance = ((pixel[:, None, :] - entries[None, :, :]) ** 2).sum(axis=-1)

        # Act
        _, _, share = dither.two_nearest(distance, spacing_of(entries), dither.MAX_DITHER)

        # Assert
        assert share.tolist() == [0]

    def test_the_share_follows_the_colour_along_the_pair_and_not_its_distance(self):
        # Arrange
        entries = np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.float32)
        pixel = np.array([[0.25, 0.5]], dtype=np.float32)
        distance = ((pixel[:, None, :] - entries[None, :, :]) ** 2).sum(axis=-1)

        # Act
        _, _, share = dither.two_nearest(distance, spacing_of(entries), dither.MAX_DITHER)

        # Assert
        assert share.tolist() == [64]

    def test_leading_axes_are_kept(self):
        # Arrange
        distance = np.ones((3, 5, 4), dtype=np.float32)
        spacing = np.ones((4, 4), dtype=np.float32)

        # Act
        nearest, runner, share = dither.two_nearest(distance, spacing, dither.MAX_DITHER)

        # Assert
        assert (nearest.shape, runner.shape, share.shape) == ((3, 5), (3, 5), (3, 5))

    def test_a_single_entry_has_no_runner_up_to_mix(self):
        # Arrange
        distance = np.array([[0.5], [2.0]], dtype=np.float32)
        spacing = np.zeros((1, 1), dtype=np.float32)

        # Act
        nearest, runner, share = dither.two_nearest(distance, spacing, dither.MAX_DITHER)

        # Assert
        assert (nearest.tolist(), runner.tolist(), share.tolist()) == ([0, 0], [0, 0], [0, 0])


class TestMix:
    def test_a_ramp_between_two_entries_uses_both(self):
        # Arrange
        nearest, runner, share = dither.two_nearest(
            ramp_distance(64), PAIR_SPACING, dither.MAX_DITHER
        )
        threshold = dither.bayer_thresholds(SMS_TILE).reshape(-1)

        # Act
        picked = dither.mix(nearest, runner, share, threshold)

        # Assert
        assert np.unique(picked).tolist() == [0, 1]

    def test_more_of_the_far_end_lands_on_the_far_entry(self):
        # Arrange
        nearest, runner, share = dither.two_nearest(
            ramp_distance(64), PAIR_SPACING, dither.MAX_DITHER
        )
        threshold = dither.bayer_thresholds(SMS_TILE).reshape(-1)

        # Act
        picked = dither.mix(nearest, runner, share, threshold)

        # Assert
        assert int(picked[:32].sum()) < int(picked[32:].sum())

    def test_strength_zero_picks_the_nearest_everywhere(self):
        # Arrange
        distance = ramp_distance(64)
        nearest, runner, share = dither.two_nearest(distance, PAIR_SPACING, dither.NO_DITHER)
        threshold = dither.bayer_thresholds(SMS_TILE).reshape(-1)

        # Act
        picked = dither.mix(nearest, runner, share, threshold)

        # Assert
        assert np.array_equal(picked, np.argmin(distance, axis=1))

    def test_a_weaker_dither_swaps_fewer_pixels(self):
        # Arrange
        distance = ramp_distance(64)
        threshold = dither.bayer_thresholds(SMS_TILE).reshape(-1)
        plain = np.argmin(distance, axis=1)
        half = dither.mix(*dither.two_nearest(distance, PAIR_SPACING, 0.5), threshold)

        # Act
        full = dither.mix(*dither.two_nearest(distance, PAIR_SPACING, dither.MAX_DITHER), threshold)

        # Assert
        assert 0 < int((half != plain).sum()) < int((full != plain).sum())


class TestStrength:
    @pytest.mark.parametrize("strength", [-0.1, 1.1], ids=["negative", "past-the-maximum"])
    def test_a_strength_outside_the_range_is_refused(self, strength):
        # Arrange
        distance = ramp_distance(4)

        # Act
        with pytest.raises(ValueError) as refused:
            dither.two_nearest(distance, PAIR_SPACING, strength)

        # Assert
        assert str(refused.value) == f"a dither strength lies between 0 and 1, got {strength:g}"


LINE = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
TRIANGLE = np.array([[0.2, 0.0, 0.0], [0.8, 0.3, 0.0], [0.8, -0.3, 0.0]])


class TestPatternCandidates:
    def test_a_colour_on_an_entry_draws_only_that_entry(self):
        # Arrange
        point = LINE[1][None, :]

        # Act
        candidates = dither.pattern_candidates(point, LINE, strength=1.0)

        # Assert
        assert candidates.tolist() == [[1, 1, 1, 1]]

    def test_a_colour_midway_between_two_entries_draws_each_half_the_time(self):
        # Arrange
        point = np.array([[0.5, 0.0, 0.0]])

        # Act
        candidates = dither.pattern_candidates(point, LINE, strength=1.0)

        # Assert
        assert candidates.tolist() == [[0, 0, 1, 1]]

    def test_candidates_come_darkest_first(self):
        # Arrange
        point = np.array([[0.3, 0.0, 0.0]])

        # Act
        candidates = dither.pattern_candidates(point, LINE, strength=1.0)

        # Assert
        assert candidates[0].tolist() == sorted(candidates[0].tolist())

    def test_no_strength_draws_the_nearest_entry_every_time(self):
        # Arrange
        point = np.array([[0.3, 0.0, 0.0]])

        # Act
        candidates = dither.pattern_candidates(point, LINE, strength=0.0)

        # Assert
        assert candidates.tolist() == [[0, 0, 0, 0]]

    def test_a_colour_off_every_pair_is_drawn_closer_than_the_two_entry_mix_draws_it(self):
        # Arrange
        point = TRIANGLE.mean(axis=0)
        field = dither.bayer_thresholds(SMS_TILE).reshape(-1)
        distance = ((point[None, :] - TRIANGLE) ** 2).sum(axis=-1)[None, :].repeat(field.size, 0)
        nearest, runner, share = dither.two_nearest(distance, spacing_of(TRIANGLE), 1.0)
        mixed = TRIANGLE[dither.mix(nearest, runner, share, field)].mean(axis=0)

        # Act
        candidates = dither.pattern_candidates(point[None, :], TRIANGLE, strength=1.0, count=16)

        # Assert
        drawn = TRIANGLE[candidates[0]].mean(axis=0)
        assert np.linalg.norm(drawn - point) < np.linalg.norm(mixed - point)

    def test_asking_for_no_candidates_is_refused(self):
        # Arrange
        point = np.array([[0.3, 0.0, 0.0]])

        # Act
        with pytest.raises(ValueError) as refused:
            dither.pattern_candidates(point, LINE, strength=1.0, count=0)

        # Assert
        assert str(refused.value) == "a pattern needs at least one candidate, got 0"

    def test_a_strength_outside_the_range_is_refused(self):
        # Arrange
        point = np.array([[0.3, 0.0, 0.0]])

        # Act
        with pytest.raises(ValueError) as refused:
            dither.pattern_candidates(point, LINE, strength=1.5)

        # Assert
        assert str(refused.value) == "a dither strength lies between 0 and 1, got 1.5"


class TestPatternPick:
    def test_the_threshold_picks_the_candidate_of_its_rank(self):
        # Arrange
        candidates = np.array([[5, 6, 7, 8]] * 4, dtype=np.uint8)
        threshold = np.array([0.1, 0.3, 0.6, 0.9], dtype=np.float32)

        # Act
        picked = dither.pattern_pick(candidates, threshold)

        # Assert
        assert picked.tolist() == [5, 6, 7, 8]

    def test_leading_axes_are_kept(self):
        # Arrange
        candidates = np.zeros((3, 64, 4), dtype=np.uint8)

        # Act
        picked = dither.pattern_pick(candidates, dither.bayer_thresholds(SMS_TILE).reshape(-1))

        # Assert
        assert picked.shape == (3, 64)
