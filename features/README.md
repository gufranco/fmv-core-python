Both players are built to the same feature list, set in [FAMILY.md](../FAMILY.md),
and this table is the same in both READMEs. "Planned" is work not done yet. A
feature a console cannot carry would say "Not possible" with the hardware reason;
none does today.

| Feature | Neo Geo | Master System |
|---|---|---|
| One command from a video file to a cartridge | Yes | Yes |
| The picture fills the screen, scaled to cover and cropped | Yes. `--fit letterbox` still exists and is due to go | Yes |
| Black bars baked into a source are found and cropped | Yes | Yes |
| Picture and sound step down from the best until the film fits | Yes. `--quality search` bakes down a 35-rung ladder, and sound takes the highest rate that still fits | Planned. Rate, denoise and reuse are measured per bake, but nothing yet steps the film down to fit the cartridge |
| The largest standard cartridge, no added hardware | Yes, 128 MiB of character ROM | Yes, 1 MB, the most any Sega mapper revision decodes |
| Ordered dithering | Yes, `--dither` | Yes, on by default |
| Palettes refit as the film changes | Yes, per scene | Yes, per frame, kept while they still fit |
| Sound with no added hardware | Yes, ADPCM-B on the YM2610 | Yes, tone synthesis on the PSG |
| A silent build that gives sound's room to the picture | Partly. A library bundle can leave sound out; sound has its own ROM, so leaving it out frees no picture room | Yes, `--silent` |
| Subtitles from a SubRip file | Yes | Yes, burned into the picture, so they cannot be switched off |
| Play and pause | Yes | Yes. Pause on the console, Start on a Game Gear |
| Fast forward and rewind | Yes, forward at 2x, 5x and 10x | Not possible: the replay already spends about 90% of every field moving one frame, so it cannot move two; Left and Right jump between seek points instead |
| Seek | Yes, 10 seconds back or forward | Yes, Left and Right jump between points 10 seconds apart |
| A position bar with elapsed and total time | Yes | Yes, while paused |
| Restart and stop | Yes | Yes |
| Sound on and off | Yes | Yes, Up |
| The film loops at the end | Yes | Yes |
| A diagnostics overlay | Yes | Yes, button 1 while paused |
| A fault screen for a corrupt stream | Yes | Yes |
| A film inside your own game | Yes, `--bundle` emits a drop-in library | Yes, `--bundle` emits a drop-in library and `examples/cutscene` builds a game from it |
| A preview of what the console will draw | Yes, a video | Yes, a video, or four frames beside their source |
| A write-timing gate on every build | Yes | Yes |
| A regression set of films baked on every test run | Yes, six films | Yes, six films |
| Run on the original hardware | Yes, AES and MVS | Not yet. A Game Gear run is pending |
