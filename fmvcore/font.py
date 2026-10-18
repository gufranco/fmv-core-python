from __future__ import annotations

import functools
import json
from importlib import resources
from typing import Final

RESOURCE: Final = "glyphs.json"
SIZE: Final = 8
INK: Final = "#"
PANEL: Final = "."
ACCENT: Final = "*"
DIM: Final = "-"
EDGE: Final = "="
BLANK: Final = "blank"
MENU_COLOURS: Final = {
    INK: (31, 31, 31),
    PANEL: (1, 1, 3),
    ACCENT: (31, 18, 2),
    DIM: (13, 13, 15),
    EDGE: (7, 7, 9),
}
MENU_LEVELS: Final = 31
PUNCTUATION: Final = {
    " ": "blank",
    ".": "dot",
    "-": "dash",
    "%": "percent",
    ":": "colon",
    "/": "slash",
    ",": "comma",
    "'": "apostrophe",
    "?": "question",
    "!": "bang",
}


def parse_art(text: str) -> dict[str, tuple[str, ...]]:
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        msg = f"{RESOURCE} must map glyph names to rows"
        raise TypeError(msg)
    return {str(name): tuple(str(row) for row in rows) for name, rows in loaded.items()}


@functools.cache
def glyph_art() -> dict[str, tuple[str, ...]]:
    return parse_art(resources.files("fmvcore").joinpath(RESOURCE).read_text("utf-8"))


def glyph_name(character: str) -> str:
    art = glyph_art()
    if character in PUNCTUATION:
        return PUNCTUATION[character]
    if character in art:
        return character
    return character.upper() if character.upper() in art else BLANK


def ink(character: str) -> tuple[tuple[bool, ...], ...]:
    rows = glyph_art()[glyph_name(character)]
    return tuple(tuple(code == INK for code in row) for row in rows)
