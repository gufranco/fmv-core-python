from __future__ import annotations

import pytest

from fmvcore import bundle
from fmvcore.testing import seeded

FAKE = seeded()


class TestCopyFiles:
    def test_every_named_file_lands_in_the_target(self, tmp_path):
        # Arrange
        source, target = tmp_path / "from", tmp_path / "to"
        source.mkdir()
        body = FAKE.sentence()
        (source / "a.c").write_text(body)

        # Act
        copied = bundle.copy_files(("a.c",), source, target, required=True)

        # Assert
        assert (copied, (target / "a.c").read_text()) == ([target / "a.c"], body)

    def test_a_missing_required_file_is_refused(self, tmp_path):
        # Arrange
        source = tmp_path / "from"
        source.mkdir()

        # Act
        with pytest.raises(FileNotFoundError) as refused:
            bundle.copy_files(("gone.c",), source, tmp_path / "to", required=True)

        # Assert
        assert str(refused.value) == f"the bundle needs gone.c, which is not in {source}"

    def test_a_missing_optional_file_is_skipped(self, tmp_path):
        # Arrange
        source = tmp_path / "from"
        source.mkdir()

        # Act
        copied = bundle.copy_files(("gone.c",), source, tmp_path / "to", required=False)

        # Assert
        assert copied == []


class TestRender:
    def test_fields_fill_the_template(self, tmp_path):
        # Arrange
        template = tmp_path / "guide.md"
        template.write_text("{banks} banks of {name}")
        name = FAKE.word()

        # Act
        text = bundle.render(template, {"banks": 4, "name": name})

        # Assert
        assert text == f"4 banks of {name}"
