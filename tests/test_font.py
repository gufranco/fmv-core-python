from __future__ import annotations

import pytest

from fmvcore import font

ONE = (
    "........",
    "...##...",
    "..###...",
    "...##...",
    "...##...",
    "...##...",
    "..####..",
    "........",
)


class TestGlyphName:
    @pytest.mark.parametrize(
        ("character", "name"), [(" ", "blank"), (".", "dot"), ("a", "a"), ("7", "7")]
    )
    def test_a_character_maps_to_its_glyph(self, character, name):
        # Arrange
        wanted = name

        # Act
        found = font.glyph_name(character)

        # Assert
        assert found == wanted

    def test_a_character_the_font_lacks_falls_back_to_blank(self):
        # Arrange
        character = "é"

        # Act
        found = font.glyph_name(character)

        # Assert
        assert found == "blank"


class TestInk:
    def test_ink_follows_the_hash_marks_of_the_art(self):
        # Arrange
        expected = tuple(tuple(code == "#" for code in row) for row in ONE)

        # Act
        found = font.ink("1")

        # Assert
        assert found == expected

    def test_every_glyph_is_eight_by_eight(self):
        # Arrange
        art = font.glyph_art()

        # Act
        sizes = {(len(rows), *{len(row) for row in rows}) for rows in art.values()}

        # Assert
        assert sizes == {(font.SIZE, font.SIZE)}


class TestParseArt:
    def test_art_that_is_not_a_mapping_is_refused(self):
        # Arrange
        text = "[]"

        # Act
        with pytest.raises(TypeError) as refused:
            font.parse_art(text)

        # Assert
        assert str(refused.value) == "glyphs.json must map glyph names to rows"
