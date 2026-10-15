from __future__ import annotations

from dataclasses import dataclass

import pytest

from fmvcore import testing

REQUIRED_ENV = "FMVCORE_TEST_TOOLS_REQUIRED"
MARKER = "tool"
MISSING = "no-such-tool-anywhere"


@dataclass(frozen=True, slots=True)
class Marked:
    marked: bool

    def get_closest_marker(self, name: str) -> object | None:
        return object() if self.marked and name == MARKER else None


def gate(item: Marked, tools: tuple[str, ...]) -> None:
    testing.require_tools(item, marker=MARKER, tools=tools, required_env=REQUIRED_ENV)


class TestSeededFakes:
    def test_two_fakes_produce_the_same_values(self):
        # Arrange
        first, second = testing.seeded(), testing.seeded()

        # Act
        values = (first.file_name(), second.file_name())

        # Assert
        assert values[0] == values[1]

    def test_the_seed_is_the_familys(self):
        # Arrange
        expected = 20261015

        # Act
        seed = testing.SEED

        # Assert
        assert seed == expected


class TestRequiredTools:
    def test_an_unmarked_test_runs_whatever_is_missing(self, monkeypatch):
        # Arrange
        monkeypatch.setenv(REQUIRED_ENV, "1")

        # Act
        outcome = gate(Marked(marked=False), (MISSING,))

        # Assert
        assert outcome is None

    def test_a_marked_test_runs_when_its_tools_are_present(self, monkeypatch):
        # Arrange
        monkeypatch.setenv(REQUIRED_ENV, "1")

        # Act
        outcome = gate(Marked(marked=True), ("python3",))

        # Assert
        assert outcome is None

    def test_a_marked_test_skips_when_a_tool_is_missing(self, monkeypatch):
        # Arrange
        monkeypatch.delenv(REQUIRED_ENV, raising=False)

        # Act
        with pytest.raises(pytest.skip.Exception) as skipped:
            gate(Marked(marked=True), (MISSING,))

        # Assert
        assert str(skipped.value) == f"{MISSING} not on the path, and this test needs it"

    def test_a_marked_test_fails_when_a_required_tool_is_missing(self, monkeypatch):
        # Arrange
        monkeypatch.setenv(REQUIRED_ENV, "1")

        # Act
        with pytest.raises(pytest.fail.Exception) as failed:
            gate(Marked(marked=True), (MISSING,))

        # Assert
        assert str(failed.value) == f"{MISSING} not on the path, and this test needs it"
