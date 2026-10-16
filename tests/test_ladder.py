from __future__ import annotations

import pytest

from fmvcore import ladder


def threshold(first: int) -> tuple[list[int], object]:
    asked: list[int] = []

    def fits(index: int) -> bool:
        asked.append(index)
        return index >= first

    return asked, fits


class TestFirstFit:
    @pytest.mark.parametrize(
        ("count", "first"), [(1, 0), (8, 0), (8, 3), (8, 7), (35, 20), (35, 34)]
    )
    def test_the_first_rung_that_fits_is_found(self, count, first):
        # Arrange
        _, fits = threshold(first)

        # Act
        found = ladder.first_fit(count, fits)

        # Assert
        assert found == first

    def test_a_ladder_where_nothing_fits_finds_nothing(self):
        # Arrange
        _, fits = threshold(99)

        # Act
        found = ladder.first_fit(35, fits)

        # Assert
        assert found is None

    def test_an_empty_ladder_finds_nothing_without_asking(self):
        # Arrange
        asked, fits = threshold(0)

        # Act
        found = ladder.first_fit(0, fits)

        # Assert
        assert (found, asked) == (None, [])

    def test_a_fit_at_the_top_is_settled_by_one_question(self):
        # Arrange
        asked, fits = threshold(0)

        # Act
        ladder.first_fit(35, fits)

        # Assert
        assert asked == [0]

    def test_thirty_five_rungs_need_at_most_eleven_questions(self):
        # Arrange
        asked, fits = threshold(23)

        # Act
        ladder.first_fit(35, fits)

        # Assert
        assert len(asked) <= 11

    def test_a_negative_count_is_refused(self):
        # Arrange
        _, fits = threshold(0)

        # Act
        with pytest.raises(ValueError) as refused:
            ladder.first_fit(-1, fits)

        # Assert
        assert str(refused.value) == "a ladder cannot have -1 rungs"
