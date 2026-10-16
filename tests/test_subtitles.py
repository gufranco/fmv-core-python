from __future__ import annotations

import pytest

from fmvcore import subtitles
from fmvcore.testing import seeded

FAKE = seeded()


def words(count: int) -> str:
    return " ".join(FAKE.words(nb=count))


def block(index: int, timing: str, *lines: str) -> str:
    return "\n".join([str(index), timing, *lines])


class TestParse:
    def test_a_cue_carries_its_times_in_seconds(self):
        # Arrange
        text = block(1, "00:01:02,500 --> 01:00:03,250", words(3))

        # Act
        cues = subtitles.parse(text)

        # Assert
        assert (cues[0].start, cues[0].end) == (62.5, 3603.25)

    def test_markup_is_stripped_from_the_lines(self):
        # Arrange
        first, second = words(2), words(2)
        text = block(1, "00:00:01,000 --> 00:00:02,000", f"<i>{first}</i>", f"{{\\an8}}{second}")

        # Act
        cues = subtitles.parse(text)

        # Assert
        assert cues[0].lines == (first, second)

    def test_a_block_with_no_timing_or_no_text_is_skipped(self):
        # Arrange
        kept = words(2)
        text = "\n\n".join(
            [
                block(1, "not a timing line", words(2)),
                block(2, "00:00:01,000 --> 00:00:02,000", "<b></b>"),
                block(3, "00:00:03,000 --> 00:00:04,000", kept),
            ]
        )

        # Act
        cues = subtitles.parse(text)

        # Assert
        assert [cue.lines for cue in cues] == [(kept,)]

    def test_windows_line_endings_separate_blocks(self):
        # Arrange
        first = block(1, "00:00:01,000 --> 00:00:02,000", "ab")
        second = block(2, "00:00:03,000 --> 00:00:04,000", "cd")
        text = (first + "\n\n" + second).replace("\n", "\r\n")

        # Act
        cues = subtitles.parse(text)

        # Assert
        assert [cue.lines for cue in cues] == [("ab",), ("cd",)]

    def test_short_millisecond_fields_are_read_as_fractions(self):
        # Arrange
        text = block(1, "00:00:01.5 --> 00:00:02.25", words(1))

        # Act
        cues = subtitles.parse(text)

        # Assert
        assert (cues[0].start, cues[0].end) == (1.5, 2.25)


class TestTrimmed:
    def test_an_overlapping_cue_ends_where_the_next_begins(self):
        # Arrange
        cues = [subtitles.Cue(1.0, 5.0, ("a",)), subtitles.Cue(3.0, 6.0, ("b",))]

        # Act
        kept = subtitles.trimmed(cues)

        # Assert
        assert [(cue.start, cue.end) for cue in kept] == [(1.0, 3.0), (3.0, 6.0)]

    def test_a_cue_left_with_no_time_is_dropped(self):
        # Arrange
        cues = [subtitles.Cue(2.0, 4.0, ("a",)), subtitles.Cue(2.0, 6.0, ("b",))]

        # Act
        kept = subtitles.trimmed(cues)

        # Assert
        assert [cue.lines for cue in kept] == [("b",)]


class TestActive:
    def test_the_cue_covering_the_moment_is_returned(self):
        # Arrange
        cues = [subtitles.Cue(1.0, 2.0, ("a",)), subtitles.Cue(2.0, 3.0, ("b",))]

        # Act
        found = subtitles.active(cues, 2.0)

        # Assert
        assert found == cues[1]

    def test_a_moment_between_cues_has_none(self):
        # Arrange
        cues = [subtitles.Cue(1.0, 2.0, ("a",))]

        # Act
        found = subtitles.active(cues, 2.5)

        # Assert
        assert found is None


class TestLayout:
    def test_text_wraps_at_the_column_count(self):
        # Arrange
        text = "aaaa bbbb cccc"

        # Act
        lines = subtitles.layout(text, columns=9, max_lines=2)

        # Assert
        assert lines == ("aaaa bbbb", "cccc")

    def test_lines_past_the_limit_are_dropped(self):
        # Arrange
        text = "aa bb cc"

        # Act
        lines = subtitles.layout(text, columns=2, max_lines=2)

        # Assert
        assert lines == ("aa", "bb")

    def test_a_layout_with_no_room_is_refused(self):
        # Arrange
        text = words(2)

        # Act
        with pytest.raises(ValueError) as refused:
            subtitles.layout(text, columns=0, max_lines=2)

        # Assert
        assert str(refused.value) == "a subtitle needs at least one column and one line, got 0x2"


class TestSidecar:
    def test_a_srt_beside_the_source_is_found(self, tmp_path):
        # Arrange
        source = tmp_path / "film.mp4"
        (tmp_path / "film.srt").write_text("")

        # Act
        found = subtitles.sidecar_for(source)

        # Assert
        assert found == tmp_path / "film.srt"

    def test_no_srt_beside_the_source_gives_none(self, tmp_path):
        # Arrange
        source = tmp_path / "film.mp4"

        # Act
        found = subtitles.sidecar_for(source)

        # Assert
        assert found is None
