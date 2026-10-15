# Design notes

Why each module of the core is shaped as it is. Source files carry no comments
or docstrings, so the reasoning lives here, one section per module.
[AGENTS.md](AGENTS.md) is the engineering contract and the
[README](README.md) says what the core is and how a player uses it.

## [`fmvcore/writetiming.py`](fmvcore/writetiming.py)

The cheapest path, in cycles, from every write to a console port to every write
it can reach next, across a whole program.

Both players write their video hardware under documented minimum spacings that
no emulator enforces, so each build is checked against the instructions it
actually emitted. This module does the walking and knows nothing about any
processor: a reader turns a listing into instructions that already carry their
cost taken and not taken, whether they branch, call, return or never fall
through, and which port, if any, they write. The player then holds each gap
against its own floors.

Branches are followed both ways, so a loop is measured along the path it takes
rather than as the sum of every instruction in its range. A call reaches the
callee's first instruction, a return reaches the instruction after every call
site of its function or of any function that tail-jumps into it, and a tail
jump out of the listings returns to the caller. A call to code outside the
listings is charged its own cycles only, which can only make a path look
faster. Each walk is a Dijkstra search bounded by the program's edge count; a
walk that does not settle inside that bound raises rather than passing.

A repeating block output, such as the Z80's `otir`, writes at its own interval
with no instruction between, so the reader marks it and the walker reports it
as a gap with itself.

## [`fmvcore/sdccz80.py`](fmvcore/sdccz80.py)

Read an SDCC Z80 assembler listing into the walker's instructions.

The cycle counts are the assembler's, printed in brackets against every
instruction, so no cycle table is kept here to disagree with the toolchain. The
only figures of its own are what a conditional branch costs when not taken,
which the listing does not print.

The caller passes its port map, so the reader names no console. A block output
writes through register C, so the reader follows the last constant loaded into
it, forgets it when anything else touches C or a new function starts, and
charges the caller's chosen port when it cannot know.

SDCC reuses local labels such as `00104$` in every function, so a local label
is scoped to the function that owns it. A function starts at a global label or
at any label something calls or jumps to with the function prefix; a data
label inside a function, such as a string, owns no code.

## [`fmvcore/m68kobjdump.py`](fmvcore/m68kobjdump.py)

Read GNU objdump disassembly of 68000 objects into the walker's program, and
turn the walker's gaps into the spacing between bus accesses.

objdump prints no cycle counts, so the reader keeps a table of the instructions
the players emit and charges four cycles, the shortest 68000 instruction, for
anything else. Undercounting reports a pair as closer than it is, so an
instruction missing from the table can only make the gate stricter.

A 68000 write reaches the bus partway through its instruction, and a long write
reaches it twice, one word at the address and the next word two bytes on. Each
modelled write form carries the offsets of those accesses, so the spacing
between two writes is measured from the end of the first one's last bus cycle
to the start of the next one's first. A write form outside the model is
refused rather than given a guess.

The objects are read with relocations, `objdump -dr`, because an unlinked call
prints as `jsr 0` with the callee only in the relocation that follows. A call
through a section symbol rather than a named function is refused, since the
walker resolves calls by name. A call through a register cannot be followed and
costs its own cycles before falling through.

## [`fmvcore/libretro.py`](fmvcore/libretro.py)

Run any libretro core from Python with no window, no sound and no front end,
and keep the frames it draws.

The family's evidence comes from emulators, and an emulator that opens a window
takes the owner's screen while they work. Driving the core's C entry points
directly removes the window by construction rather than by a flag that one
platform ignores: geolith captures the Neo Geo player this way, and any other
libretro core can stand in for another console.

The host answers the handful of environment calls a core needs to start: the
system and save directories, the pixel format, the duplicate-frame capability,
and core options. A core declares its options with their defaults, and the host
answers each query with the caller's value or that default, because a core that
gets no answer may leave a setting unset. geolith drew a black screen until
this was answered. Every other call is refused, which a well-behaved core
treats as an older front end.

A duplicated frame, a null pointer from the core, repeats the last picture, so
the frame index always matches the core's own frame count. Only the indices the
caller keeps are copied out, because a run of thousands of frames would
otherwise hold every one of them in memory.

The C callbacks can only report back by writing to a session object, so that
object is mutable by design, and the callback objects are held for the whole
run, since ctypes frees a callback the moment nothing references it.

The tests build a small C core from [`tests/fixtures/testcore.c`](tests/fixtures/testcore.c)
with the system compiler, so the host is tested against real C calls without
downloading an emulator.

## [`fmvcore/testing.py`](fmvcore/testing.py)

What every member's tests share.

`seeded` returns a Faker seeded with the family's one seed, so a value that
does not matter to a test is still the same value on every run and every
machine. `require_tools` is the body of a `pytest_runtest_setup` hook: a test
carrying the given marker skips when one of its tools is missing, and fails
instead when the named environment variable is `1`, which CI and the
pre-commit hooks set. A test that silently skipped in CI would report a gate
as passed that never ran.

It imports pytest and Faker, which every member already has as test
dependencies, so only test code imports it.

## [`fmvcore/arguments.py`](fmvcore/arguments.py)

Command-line values checked where they enter, so a bad one never bakes.

In the Master System player a rate of zero divided by zero deep inside
pacing, a negative one paced every frame to a single field, and a reuse
threshold of NaN baked a ROM. Each of those is refused here with the range it
had to lie in. The ranges belong to the player; this module only holds the
shape of the check and its messages, so both players refuse a bad value in
the same words.

`number_or_auto` keeps the text it was given rather than the parsed number,
because a player that searches for a value when told `auto` decides what
`auto` means later, and a number must reach it unchanged.

## [`fmvcore/capture.py`](fmvcore/capture.py)

Compare what a screen showed, field by field, with the film it came from.

Each player replays its own stream into `Played`: the picture after every
field, and the fields on which a frame completed. That replay is the player's,
because only the player knows its stream. What is measured on it is shared.

`align` finds the offset at which an emulator recording repeats the replay
exactly, sampling up to 48 fields across up to 64 offsets. The final field is
left out, because what follows the last frame is the player's end-of-film
handling, which the stream does not describe: a player that reset the screen
on that field measured as a mismatch on a capture that was otherwise exact.

`mixed_share` is the share of pixels, during a transfer, that match neither
the frame before nor the frame after. It is the glitch at a cut, and a clean
transfer scores zero.

`measured_lags` matches each completed frame against the source within a
window, on 8 by 8 thumbnails, and reports how many fields late it appeared.
The lag is measured rather than taken from the encoder, so it checks the
schedule instead of trusting it.

## [`fmvcore/clips.py`](fmvcore/clips.py)

How to know a copy of a film is the one a manifest names.

A regression set has to name films the repository cannot carry, so a player
carries their identity instead: a SHA-256 that decides accept or reject, a
byte count that rejects the wrong file for one stat call, and a CRC-32 and
SHA-1 that let a copy be cross-checked against a public index.

`verify` takes any record with the identity fields, the `Film` protocol, so
each player keeps its own manifest schema and the per-film expectations it
measures, and both check identity the same way. SHA-256 decides. The size is
checked first because it rejects the wrong file without reading it, and
because the two failures mean different things: a size that does not match is
a different film, while a size that matches with a digest that does not is
the right film re-encoded, cut or corrupted. Saying which is what turns a
refusal into something the reader can act on, and every refusal ends with the
player's own fetch command.

A film with no published digest is refused outright, because nothing can
recognise a copy of it.

## [`fmvcore/fetch.py`](fmvcore/fetch.py)

Fetch a film the manifest names and keep it only if it verifies.

Nothing downloads on its own: a player's fetch script calls `acquire` for the
films it wants. The download goes to a `.part` file beside the target and is
renamed over it only after it verifies, so a half-right file never sits where
the next run would report it present. A committed film is checked and never
downloaded, and a stale copy is replaced rather than kept.

A connection reset, a timeout or a torn read is retried up to three times,
waiting five and then ten seconds. A download larger than the manifest's byte
count, or one that never ends, is refused at once and never retried, because a
retry would only fetch the same wrong thing again. The block ceiling and block
size are parameters so a test can reach the never-ending case without a
four-gigabyte stream.

## [`fmvcore/colour.py`](fmvcore/colour.py)

How far a picture is from its source, measured the same way in both players.

Distances are taken in Oklab, with Bjorn Ottosson's published matrices, so a
step in any direction is roughly a step a viewer sees. `srgb_to_oklab` takes
sRGB scaled to 0 to 1 and refuses an array whose last axis is not three
channels, because a frame passed without its channel axis converts without
complaint into nonsense.

The conversion runs in float64 and returns float32, as two matrix products,
the form the Neo Geo player used. The two players had computed it differently,
one in float32 with the sums written out, and the two disagreed by one rounding
step on 31 of the 98,304 values over the Neo Geo's colour grid, enough to flip
near-tied colour choices. Taking the more precise form leaves the Neo Geo's
bakes byte-identical and moves the Master System's by those near-ties, which
its picture tests and the regression set accept.

`oklab_error` is the mean per-pixel distance, and it is the right number for
a picture with no dither. A dither moves pixels away from the source on
purpose, so the per-pixel number always scores it as loss. `blurred_error`
first runs the same separable 1, 4, 6, 4, 1 low-pass over both sides, edges
extended, and then measures. A checkerboard of black and white then scores as
the grey at its Oklab midpoint, which is what the eye makes of it. The
family judges a dither by both numbers and by a rendered sheet, never by the
blurred number alone, because two changes have won on it and looked worse on
screen.

It refuses frames of different shapes and a single frame without its batch
axis, because either would broadcast into a plausible number that compares
the wrong pixels.

## [`fmvcore/ffmpeg.py`](fmvcore/ffmpeg.py)

Drive ffmpeg to produce frames, and refuse every way a decode can go quietly
wrong.

Decoding streams rather than materialising the whole film, because a bake
holds one frame plus its working set rather than the movie. The caller owns
the filter chain: each player scales, crops and denoises for its own raster,
and the core only joins the stages, runs them and cuts the output into frames
of the shape the caller names.

The error stream goes to a temporary file. A pipe holds about 64 KB, and a
decoder that fills it blocks writing errors while the reader blocks waiting for
frames, so neither side moves. A file has no such limit, and what ffmpeg said
is still there to quote when it fails.

The frame ceiling is a parameter, not a constant. A player knows the longest
film it accepts and the rate it decodes at, so it sets the ceiling; the core
only guarantees the loop stops there and says so by name.

`source_info` reads ffprobe's JSON and refuses anything that is not a film: no
video stream, a zero or infinite duration, a non-positive frame rate or a
rate of `0/0`. Each refusal names the file, because a bake usually walks
several.

## [`fmvcore/hook.py`](fmvcore/hook.py)

Run a member's pre-commit checks and refuse the commit when one fails.

Every member had its own copy of the same loop, and the copies had started to
drift. The loop lives here and each repository's hook keeps only its list:
the checks that always run, the player checks that run only when a staged path
can change what reaches the console, and the environment that makes a skipped
test fail instead. The module uses only the standard library, because a hook
runs under the system Python before any project environment exists.

