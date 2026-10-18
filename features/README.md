Both players are built to the same feature list, set in [FAMILY.md](../FAMILY.md),
and this table is the same in both READMEs. "Planned" is work not done yet. A
feature a console cannot carry says "Not possible" with the hardware reason.

| Feature | Neo Geo | Master System | Game Gear |
|---|---|---|---|
| One command from a video file to a cartridge | Yes | Yes | Yes, `--target gg` |
| The picture fills the screen, scaled to cover and cropped | Yes | Yes | Yes, the 160 by 144 panel |
| Black bars baked into a source are found and cropped | Yes | Yes | Yes |
| Picture and sound step down from the best until the film fits | Yes. `--quality search` bakes down a 35-rung ladder, and sound takes the highest rate that still fits | Yes. A bake that overruns the cartridge steps the frame rate down through the same search, and sound goes last | Yes, the same search as the Master System |
| The largest standard cartridge, no added hardware | Yes, 128 MiB of character ROM | Yes, 1 MB, the most any Sega mapper revision decodes | Yes, 1 MB, the same mapper |
| Ordered dithering | Yes, `--dither`, off by default | Yes, `--dither`, on by default | Yes, `--dither`, on by default |
| Palettes refit as the film changes | Yes, per scene | Yes, per frame, kept while they still fit | Yes, per frame, from 4096 colours |
| Sound with no added hardware | Yes, ADPCM-B on the YM2610 | Yes, tone synthesis on the PSG | Yes, tone synthesis on the PSG, routed left and right on the headphones from a stereo source |
| A silent build that gives sound's room to the picture | Yes, `--silent`. Sound has its own ROM, so leaving it out frees no picture room | Yes, `--silent` | Yes, `--silent` |
| Subtitles from a SubRip file | Yes | Yes, burned into the picture, so they cannot be switched off | Yes, burned into the picture, so they cannot be switched off |
| Play and pause | Yes | Yes. Pause on the console, Start on a Game Gear | Yes, Start |
| Fast forward and rewind | Yes, forward at 2x, 5x and 10x | Not possible: moving one frame already takes up to 54,000 of a field's 59,736 T-states, so the replay cannot move two; Left and Right jump between seek points instead | Not possible, for the Master System's reason: one frame takes up to 54,000 of a field's 59,736 T-states |
| Seek | Yes, C and D jump between points 10 seconds apart, `--seek-every` to change | Yes, Left and Right jump between points 10 seconds apart, `--seek-every` to change | Yes, Left and Right jump between points 10 seconds apart, `--seek-every` to change |
| A position bar with elapsed and total time | Yes, for three seconds after any press | Yes, with `--menu`, for three seconds after any press, and while paused. Off by default: it keeps 4 of the film's 32 colours | Yes, with `--menu`, for three seconds after any press, and while paused. Off by default: it keeps 4 of the film's 32 colours |
| Restart and stop | Yes | Yes | Yes |
| Sound on and off | Yes | Yes, Up | Yes, Up |
| The film loops at the end | Yes | Yes | Yes |
| A diagnostics overlay | Yes, Select | Yes, Down, with `--menu` | Yes, Down, with `--menu` |
| A fault screen for a corrupt stream | Yes | Yes | Yes |
| A film inside your own game | Yes, `--bundle` emits a drop-in library | Yes, `--bundle` emits a drop-in library and `examples/cutscene` builds a game from it | Yes, `--bundle` with `--target gg` emits a Game Gear library |
| A preview of what the console will draw | Yes, a video, or four frames beside their source | Yes, a video, or four frames beside their source | Yes, a video, or four frames beside their source |
| A write-timing gate on every build | Yes | Yes | Yes |
| A regression set of films baked on every test run | Yes, six films | Yes, six films | Yes, the same six films baked into the Game Gear window |
| Run on the original hardware | Yes, AES and MVS | Yes, a Master System and a Game Gear | Planned: the Master System cartridge has run on a Game Gear, the native one has not yet |
