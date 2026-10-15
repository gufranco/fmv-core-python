# fmv-core-python

The Python code shared by two full-motion video players for consoles that were
never meant to show film:
[aes-movie-player](https://github.com/gufranco/aes-movie-player) for the Neo
Geo and [sms-movie-player](https://github.com/gufranco/sms-movie-player) for
the Sega Master System. Each player bakes a film offline into data its console
can replay, and everything in that bake that the hardware does not force lives
here once.

The family's rules, and what belongs in the core versus a player, are in
[FAMILY.md](FAMILY.md).

## What it holds

| Module | What it does |
|:--|:--|
| [`fmvcore/arguments.py`](fmvcore/arguments.py) | Command-line value types that refuse a non-number, NaN, infinity or a value outside the player's range, naming the flag, plus `auto` for a value the player searches for |
| [`fmvcore/colour.py`](fmvcore/colour.py) | sRGB to Oklab, and the per-pixel and blurred Oklab errors a bake is scored by against one fixed reference |
| [`fmvcore/ffmpeg.py`](fmvcore/ffmpeg.py) | Probes a source, builds the ffmpeg command for a filter chain, and streams whole RGB frames with a ceiling, refusing a failed decoder or a torn final frame |

More modules arrive as each shared concern moves out of the players.

## How a player uses it

A player carries this repository as a git submodule at its root and puts it on
the import path through a uv path source. It is never published as a package.

```bash
git submodule add https://github.com/gufranco/fmv-core-python.git fmv-core-python
```

```toml
[project]
dependencies = ["fmvcore"]

[tool.uv.sources]
fmvcore = { path = "../fmv-core-python", editable = true }
```

A clone of a player then needs its submodules:

```bash
git clone --recurse-submodules https://github.com/gufranco/<player>.git
```

## Working on it

It needs [uv](https://docs.astral.sh/uv/), and `ffmpeg` with `ffprobe` on the
path for the decode tests.

```bash
make hooks
uv run ruff format --check .
uv run ruff check .
uv run mypy fmvcore
FMVCORE_FFMPEG_REQUIRED=1 uv run python -m pytest --cov=fmvcore --cov-fail-under=95
```

The pre-commit hook runs the same four gates. Tests that need ffmpeg skip
without it, and fail instead when `FMVCORE_FFMPEG_REQUIRED=1` is set, which CI
and the hook set.

## Why it can be trusted

Every module here came out of a player where it already ran against real
footage, and it arrives with the tests that held it there. A change to the core
is a change to both players' output until shown otherwise, so each player runs
its golden test and regression set against a new core before moving its pin.

[AGENTS.md](AGENTS.md) is the engineering contract,
[DESIGN.md](DESIGN.md) records why each module is shaped as it is, and
[CHANGELOG.md](CHANGELOG.md) records what was tried and rejected.

## License

GPL-3.0, see [LICENSE](LICENSE).
