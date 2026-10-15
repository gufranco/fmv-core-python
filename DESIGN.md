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
