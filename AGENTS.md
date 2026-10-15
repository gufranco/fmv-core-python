# Engineering contract

The rules for changing this repository. [FAMILY.md](FAMILY.md) is the standard
every member of the family follows, and it binds here first; this file adds
what is particular to the core. [DESIGN.md](DESIGN.md) records why each module
is shaped as it is.

## What belongs here

A concern moves into the core when both players need it and no hardware forces
the two versions apart. A concern a console does force stays in that player.
When both players carry a version, the better-tested and better-guarded one
moves here, with its tests, and the other player adapts to it.

The core never names a console's binding numbers. A ceiling, a raster or a
rate is a parameter the player passes, so the core cannot drift from a figure
the player owns.

## Gates

| Claim | Command |
|:--|:--|
| Formatted | `uv run ruff format --check .` |
| Lint clean | `uv run ruff check .` |
| Types hold | `uv run mypy fmvcore` |
| Behaviour holds | `FMVCORE_FFMPEG_REQUIRED=1 uv run python -m pytest --cov=fmvcore --cov-fail-under=95` |
| A commit is clean | `.githooks/pre-commit`, installed once by `make hooks` |
| Both players still bake the same | each player's golden test and regression set against this commit |

The last row is not settled here. A change that alters a module's output is a
change to both players' output, so it is reported as unverified until each
player has run its own gates against the new commit.

## Hard rules

- No comments or docstrings in source. The reasoning goes in
  [DESIGN.md](DESIGN.md) or the commit message.
- Functions under 30 lines, files under 500.
- `mypy` strict, `ruff` clean, every loop bounded by a ceiling the caller can
  see.
- Test values that do not matter come from the seeded fakes in
  [`fmvcore/testing.py`](fmvcore/testing.py).
- Every test is Arrange, Act, Assert, each opened by its bare marker.

## Things that will bite you

- A decoder writing a megabyte to its error stream fills a pipe and hangs the
  read on its output. The error stream goes to a temporary file, never a pipe,
  and a test holds that.
- ffmpeg can end on part of a frame. A trailing partial frame is refused rather
  than dropped, because a silently shorter film is a wrong bake that looks
  right.
