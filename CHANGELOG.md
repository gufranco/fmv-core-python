# Development log

What the core tried, what it measured, and what it rejected. The
[README](README.md) says what the core is, and [RELEASES.md](RELEASES.md) is the
version history.

## The blurred error averages light

`blurred_error` ran its low-pass on Oklab values. Pixels mix as light, and the
mean of cube roots sits below the cube root of the mean, so the blur read a
dither of black and a dark level as darker than it looks. On the Master
System and Game Gear regression clips it scored a flat grey of the wrong
brightness above a correct dither in every dark scene: on the Game Gear's
Sintel fade the right picture scored 0.041 and grey blocks of a stale scene
0.016. The low-pass now runs on linear light and the Oklab error is taken
after it, which agrees with the rendered sheets on every clip checked.
`srgb_to_linear` and `linear_to_oklab` are public so a player's dither can
mix levels by their light.

## The decode path moves out of the Master System player

The first shared module is the decode path from sms-media-player, chosen over
the Neo Geo player's because it refuses more. Both of the Neo Geo player's
decodes cut a trailing partial frame off without a word. Its streaming decode
also sends ffmpeg's error stream to `/dev/null` and never reads the exit code,
so a decoder that dies early yields a short film as if nothing happened, and
its whole-clip decode pads a shortfall of up to two frames by repeating the
last one. The Master System version refuses a
partial frame, quotes what ffmpeg said, and keeps the error stream in a file so
a decoder that writes a lot of errors cannot fill a pipe and hang.

One thing changed on the way. The frame ceiling was a constant derived from
the Master System's field rate, which the core cannot know, so it became a
parameter each player passes, and its message lost the clause about four
hours at the field rate for the same reason. The private command builder and
the scaler check became public under the names `frame_command` and
`check_scaler`, so a player's own filter chain can use them.
