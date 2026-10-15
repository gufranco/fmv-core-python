# Design notes

Why each module of the core is shaped as it is. Source files carry no comments
or docstrings, so the reasoning lives here, one section per module.
[AGENTS.md](AGENTS.md) is the engineering contract and the
[README](README.md) says what the core is and how a player uses it.

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
