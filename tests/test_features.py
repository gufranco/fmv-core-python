from pathlib import Path

import pytest

FEATURES = Path(__file__).resolve().parents[1] / "features"
LANGUAGES = ("", ".ja", ".zh-Hans", ".zh-HK")


def rows(path: Path) -> int:
    return sum(1 for line in path.read_text().splitlines() if line.startswith("| "))


class TestTheSharedFeatureTable:
    @pytest.mark.parametrize("tag", LANGUAGES)
    def test_every_language_has_its_copy(self, tag):
        # Arrange
        path = FEATURES / f"README{tag}.md"

        # Act
        exists = path.is_file()

        # Assert
        assert exists is True

    @pytest.mark.parametrize("tag", LANGUAGES[1:])
    def test_every_translation_has_as_many_rows_as_the_english(self, tag):
        # Arrange
        english = rows(FEATURES / "README.md")

        # Act
        translated = rows(FEATURES / f"README{tag}.md")

        # Assert
        assert translated == english
