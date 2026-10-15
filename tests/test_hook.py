from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

from fmvcore import hook
from fmvcore.testing import seeded

PASS = (sys.executable, "-c", "raise SystemExit(0)")
FAIL = (sys.executable, "-c", "import sys; print('broken'); raise SystemExit(3)")
SHOW_FLAG = (
    sys.executable,
    "-c",
    "import os, sys; sys.exit(0 if os.environ.get('FLAG') == '1' else 1)",
)


def repository(path: Path, staged: dict[str, str]) -> Path:
    subprocess.run(("git", "init", "-q", str(path)), check=True)
    for name, text in staged.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        subprocess.run(("git", "-C", str(path), "add", name), check=True)
    return path


@pytest.fixture
def fake() -> Faker:
    return seeded()


class TestStaged:
    def test_the_staged_paths_are_listed(self, tmp_path, fake):
        # Arrange
        name = f"{fake.word()}.txt"
        root = repository(tmp_path, {name: fake.sentence(), f"src/{name}": fake.sentence()})

        # Act
        paths = hook.staged(root)

        # Assert
        assert sorted(paths) == sorted([name, f"src/{name}"])


class TestRun:
    def test_every_check_passing_lets_the_commit_through(self, tmp_path, fake):
        # Arrange
        root = repository(tmp_path, {"README.md": fake.sentence()})
        gates = hook.Gates(always=(hook.Check("format", PASS),))

        # Act
        code = hook.run(root, gates)

        # Assert
        assert code == 0

    def test_a_failing_check_refuses_the_commit_and_names_it(self, tmp_path, fake, capsys):
        # Arrange
        root = repository(tmp_path, {"README.md": fake.sentence()})
        gates = hook.Gates(always=(hook.Check("format", PASS), hook.Check("tests", FAIL)))

        # Act
        code = hook.run(root, gates)

        # Assert
        assert (code, capsys.readouterr().err) == (1, "broken\n\ncommit refused: tests\n")

    def test_player_checks_run_only_when_a_player_path_is_staged(self, tmp_path, fake):
        # Arrange
        root = repository(tmp_path, {"README.md": fake.sentence()})
        gates = hook.Gates(
            always=(hook.Check("format", PASS),),
            player=(hook.Check("rom", FAIL),),
            player_paths=("src/",),
        )

        # Act
        code = hook.run(root, gates)

        # Assert
        assert code == 0

    def test_a_staged_player_path_runs_the_player_checks(self, tmp_path, fake, capsys):
        # Arrange
        root = repository(tmp_path, {"src/main.c": fake.sentence()})
        gates = hook.Gates(
            always=(hook.Check("format", PASS),),
            player=(hook.Check("rom", FAIL),),
            player_paths=("src/",),
        )

        # Act
        code = hook.run(root, gates)

        # Assert
        assert (code, capsys.readouterr().err.splitlines()[-1]) == (1, "commit refused: rom")

    def test_the_required_environment_reaches_each_check(self, tmp_path, fake):
        # Arrange
        root = repository(tmp_path, {"src/main.c": fake.sentence()})
        gates = hook.Gates(
            always=(hook.Check("always", SHOW_FLAG),),
            player=(hook.Check("player", SHOW_FLAG),),
            player_paths=("src/",),
            always_required={"FLAG": "1"},
            player_required={"FLAG": "1"},
        )

        # Act
        code = hook.run(root, gates)

        # Assert
        assert code == 0
