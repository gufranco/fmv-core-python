# Design notes

Why each module of the core is shaped as it is. Source files carry no comments
or docstrings, so the reasoning lives here, one section per module.
[AGENTS.md](AGENTS.md) is the engineering contract and the
[README](README.md) says what the core is and how a player uses it.

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
