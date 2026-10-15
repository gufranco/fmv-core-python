# fmv-core-python

The Python code shared by two full-motion video players for consoles that were
never meant to show film:
[neogeo-media-player](https://github.com/gufranco/neogeo-media-player) for the Neo
Geo and [sms-media-player](https://github.com/gufranco/sms-media-player) for
the Sega Master System. Each player bakes a film offline into data its console
can replay, and everything in that bake that the hardware does not force lives
here once.

The family's rules, and what belongs in the core versus a player, are in
[FAMILY.md](FAMILY.md).

## What it holds

| Module | What it does |
|:--|:--|
| [`fmvcore/arguments.py`](fmvcore/arguments.py) | Command-line value types that refuse a non-number, NaN, infinity or a value outside the player's range, naming the flag, plus `auto` for a value the player searches for |
| [`fmvcore/capture.py`](fmvcore/capture.py) | Aligns an emulator recording with a replay, and measures the mixed-field share at a transfer and the lag of each frame against its source |
| [`fmvcore/clips.py`](fmvcore/clips.py) | Verifies a copy of a film against the identity its manifest publishes, saying whether it is a different film or an altered one |
| [`fmvcore/fetch.py`](fmvcore/fetch.py) | Fetches a film to a partial file, retries transient failures, refuses an oversized or endless download, and keeps the file only once it verifies |
| [`fmvcore/colour.py`](fmvcore/colour.py) | sRGB to Oklab, and the per-pixel and blurred Oklab errors a bake is scored by against one fixed reference |
| [`fmvcore/writetiming.py`](fmvcore/writetiming.py) | The cheapest path in cycles between port writes across a whole program, for any processor a reader describes |
| [`fmvcore/sdccz80.py`](fmvcore/sdccz80.py) | Reads SDCC Z80 listings for that walk, with the caller's port map |
| [`fmvcore/m68kobjdump.py`](fmvcore/m68kobjdump.py) | Reads 68000 objdump disassembly for that walk, and measures the spacing between bus accesses |
| [`fmvcore/libretro.py`](fmvcore/libretro.py) | Runs a libretro core headless, with no window or sound, and returns the frames it draws |
| [`fmvcore/testing.py`](fmvcore/testing.py) | The family's seeded Faker, and the marker gate that skips a test without its tool unless a variable requires it |
| [`fmvcore/hook.py`](fmvcore/hook.py) | The pre-commit body every member runs: its checks always, its player checks when a player path is staged |
| [`fmvcore/ffmpeg.py`](fmvcore/ffmpeg.py) | Probes a source, builds the ffmpeg command for a filter chain, and streams whole RGB frames with a ceiling, refusing a failed decoder or a torn final frame |

More modules arrive as each shared concern moves out of the players.

[`features/`](features) holds the feature table both players' READMEs carry, in
English and each translation; a player's tests compare its README against it.

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

It needs [uv](https://docs.astral.sh/uv/), `ffmpeg` with `ffprobe` on the path
for the decode tests, and a C compiler as `cc` for the libretro host tests.

```bash
make hooks
uv run ruff format --check .
uv run ruff check .
uv run mypy fmvcore
FMVCORE_FFMPEG_REQUIRED=1 FMVCORE_CC_REQUIRED=1 uv run python -m pytest --cov=fmvcore --cov-fail-under=95
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

MIT, see [LICENSE](LICENSE).
