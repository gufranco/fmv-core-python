from __future__ import annotations

import ctypes
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

RGB1555: Final = 0
XRGB8888: Final = 1
RGB565: Final = 2
ENV_GET_CAN_DUPE: Final = 3
ENV_GET_SYSTEM_DIRECTORY: Final = 9
ENV_SET_PIXEL_FORMAT: Final = 10
ENV_GET_VARIABLE: Final = 15
ENV_SET_VARIABLES: Final = 16
MAX_VARIABLES: Final = 1024
CHOICES_MARK: Final = b"; "
CHOICE_SEPARATOR: Final = b"|"
ENV_GET_SAVE_DIRECTORY: Final = 31
FIVE_BITS: Final = 0x1F
SIX_BITS: Final = 0x3F
BYTE_MASK: Final = 0xFF
CHANNEL_BITS: Final = 5
GREEN_565_BITS: Final = 6
BYTE_BITS: Final = 8

Frame = npt.NDArray[np.uint8]

ENVIRONMENT = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint, ctypes.c_void_p)
VIDEO = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_size_t)
AUDIO_SAMPLE = ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16)
AUDIO_BATCH = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t)
INPUT_POLL = ctypes.CFUNCTYPE(None)
INPUT_STATE = ctypes.CFUNCTYPE(
    ctypes.c_int16, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint
)


class Variable(ctypes.Structure):
    _fields_ = (("key", ctypes.c_char_p), ("value", ctypes.c_char_p))


class GameInfo(ctypes.Structure):
    _fields_ = (
        ("path", ctypes.c_char_p),
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_size_t),
        ("meta", ctypes.c_char_p),
    )


@dataclass(slots=True)
class _Session:
    directory: bytes
    keep: Collection[int] | None
    options: dict[bytes, bytes]
    defaults: dict[bytes, bytes] = field(default_factory=dict)
    pixel_format: int = RGB1555
    index: int = 0
    last: Frame | None = None
    kept: list[tuple[int, Frame]] = field(default_factory=list)


def capture(
    core: Path,
    content: Path,
    *,
    frames: int,
    system_dir: Path,
    keep: Collection[int] | None = None,
    options: Mapping[str, str] | None = None,
) -> list[tuple[int, Frame]]:
    if frames < 1:
        msg = f"a run needs at least one frame, got {frames}"
        raise ValueError(msg)
    if not Path(core).is_file():
        msg = f"no libretro core at {core}"
        raise FileNotFoundError(msg)
    if not Path(content).is_file():
        msg = f"no content at {content}"
        raise FileNotFoundError(msg)
    chosen = {key.encode(): value.encode() for key, value in (options or {}).items()}
    session = _Session(directory=str(system_dir).encode(), keep=keep, options=chosen)
    library = ctypes.CDLL(str(core))
    callbacks = _install(library, session)
    _play(library, Path(core), Path(content), frames)
    del callbacks
    return session.kept


def to_rgb(raw: bytes, *, width: int, height: int, pitch: int, pixel_format: int) -> Frame:
    if pixel_format == XRGB8888:
        rows = np.frombuffer(raw, dtype="<u4", count=height * pitch // 4).reshape(height, -1)
        words = rows[:, :width]
        return np.stack([(words >> shift) & BYTE_MASK for shift in (16, 8, 0)], -1).astype(np.uint8)
    if pixel_format in (RGB565, RGB1555):
        rows = np.frombuffer(raw, dtype="<u2", count=height * pitch // 2).reshape(height, -1)
        return _sixteen_bit(
            rows[:, :width].astype(np.uint32),
            green_bits=GREEN_565_BITS if pixel_format == RGB565 else CHANNEL_BITS,
        )
    msg = f"pixel format {pixel_format} is not one libretro defines"
    raise ValueError(msg)


def _sixteen_bit(words: npt.NDArray[np.uint32], *, green_bits: int) -> Frame:
    blue = (words & FIVE_BITS).astype(np.uint32)
    green = (
        (words >> CHANNEL_BITS) & (SIX_BITS if green_bits == GREEN_565_BITS else FIVE_BITS)
    ).astype(np.uint32)
    red = ((words >> (CHANNEL_BITS + green_bits)) & FIVE_BITS).astype(np.uint32)
    channels = [
        _widen(red, CHANNEL_BITS),
        _widen(green, green_bits),
        _widen(blue, CHANNEL_BITS),
    ]
    return np.stack(channels, -1).astype(np.uint8)


def _widen(value: npt.NDArray[np.uint32], bits: int) -> npt.NDArray[np.uint32]:
    widened = (value << (BYTE_BITS - bits)) | (value >> (2 * bits - BYTE_BITS))
    return widened.astype(np.uint32)


def _install(library: ctypes.CDLL, session: _Session) -> tuple[object, ...]:
    callbacks = (
        ENVIRONMENT(lambda command, data: _environment(session, command, data)),
        VIDEO(lambda data, width, height, pitch: _video(session, data, width, height, pitch)),
        AUDIO_SAMPLE(lambda _left, _right: None),
        AUDIO_BATCH(lambda _data, frames: frames),
        INPUT_POLL(lambda: None),
        INPUT_STATE(lambda _port, _device, _index, _id: 0),
    )
    names = (
        "environment",
        "video_refresh",
        "audio_sample",
        "audio_sample_batch",
        "input_poll",
        "input_state",
    )
    for name, callback in zip(names, callbacks, strict=True):
        getattr(library, f"retro_set_{name}")(callback)
    return callbacks


def _play(library: ctypes.CDLL, core: Path, content: Path, frames: int) -> None:
    payload = content.read_bytes()
    buffer = ctypes.create_string_buffer(payload, len(payload))
    game = GameInfo(str(content).encode(), ctypes.cast(buffer, ctypes.c_void_p), len(payload), None)
    library.retro_load_game.restype = ctypes.c_bool
    library.retro_init()
    try:
        if not library.retro_load_game(ctypes.byref(game)):
            msg = f"{core.name} refused {content}"
            raise RuntimeError(msg)
        for _ in range(frames):
            library.retro_run()
        library.retro_unload_game()
    finally:
        library.retro_deinit()


def _environment(session: _Session, command: int, data: int | None) -> bool:
    handler = _HANDLERS.get(command)
    if data is None or handler is None:
        return False
    return handler(session, data)


def _directory(session: _Session, data: int) -> bool:
    ctypes.cast(data, ctypes.POINTER(ctypes.c_char_p))[0] = session.directory
    return True


def _pixel_format(session: _Session, data: int) -> bool:
    session.pixel_format = ctypes.cast(data, ctypes.POINTER(ctypes.c_int))[0]
    return session.pixel_format in (RGB1555, XRGB8888, RGB565)


def _set_variables(session: _Session, data: int) -> bool:
    session.defaults = _declared(data)
    return True


def _can_dupe(_session: _Session, data: int) -> bool:
    ctypes.cast(data, ctypes.POINTER(ctypes.c_bool))[0] = True
    return True


def _video(session: _Session, data: int | None, width: int, height: int, pitch: int) -> None:
    if data is not None:
        raw = ctypes.string_at(data, height * pitch)
        session.last = to_rgb(
            raw, width=width, height=height, pitch=pitch, pixel_format=session.pixel_format
        )
    index = session.index
    session.index = index + 1
    if session.last is None or (session.keep is not None and index not in session.keep):
        return
    session.kept = [*session.kept, (index, session.last.copy())]


def _variable(session: _Session, data: int) -> bool:
    variable = ctypes.cast(data, ctypes.POINTER(Variable)).contents
    key = variable.key or b""
    value = session.options.get(key, session.defaults.get(key))
    if value is None:
        return False
    variable.value = value
    return True


def _declared(data: int) -> dict[bytes, bytes]:
    variables = ctypes.cast(data, ctypes.POINTER(Variable))
    found: dict[bytes, bytes] = {}
    for index in range(MAX_VARIABLES):
        entry = variables[index]
        if entry.key is None:
            return found
        choices = (entry.value or b"").partition(CHOICES_MARK)[2]
        found = {**found, entry.key: choices.split(CHOICE_SEPARATOR)[0]}
    msg = f"a core declared more than {MAX_VARIABLES} options without ending the list"
    raise ValueError(msg)


_HANDLERS: Final[dict[int, Callable[[_Session, int], bool]]] = {
    ENV_GET_SYSTEM_DIRECTORY: _directory,
    ENV_GET_SAVE_DIRECTORY: _directory,
    ENV_SET_PIXEL_FORMAT: _pixel_format,
    ENV_SET_VARIABLES: _set_variables,
    ENV_GET_VARIABLE: _variable,
    ENV_GET_CAN_DUPE: _can_dupe,
}
