from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    command: Sequence[str]


@dataclass(frozen=True, slots=True)
class Gates:
    always: tuple[Check, ...]
    player: tuple[Check, ...] = ()
    player_paths: tuple[str, ...] = ()
    always_required: Mapping[str, str] = field(default_factory=dict)
    player_required: Mapping[str, str] = field(default_factory=dict)


def staged(root: Path) -> list[str]:
    done = subprocess.run(
        ("git", "diff", "--cached", "--name-only"),
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.split()


def run(root: Path, gates: Gates) -> int:
    touched = any(path.startswith(gates.player_paths) for path in staged(root))
    failed = _failures(root, gates.always, gates.always_required)
    if touched:
        failed = [*failed, *_failures(root, gates.player, gates.player_required)]
    if failed:
        sys.stderr.write(f"\ncommit refused: {', '.join(failed)}\n")
        return 1
    return 0


def _failures(root: Path, checks: tuple[Check, ...], required: Mapping[str, str]) -> list[str]:
    environment = {**os.environ, **required}
    failed: list[str] = []
    for check in checks:
        done = subprocess.run(
            tuple(check.command),
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        if done.returncode != 0:
            failed = [*failed, check.name]
            sys.stderr.write(done.stdout)
            sys.stderr.write(done.stderr)
    return failed
