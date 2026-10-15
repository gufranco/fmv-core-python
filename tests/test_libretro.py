from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from fmvcore import libretro

FIXTURE = Path(__file__).parent / "fixtures" / "testcore.c"
SUFFIX = ".dylib" if sys.platform == "darwin" else ".so"
SEED = 40
ANSWERED = 0x80 | 0x40 | 0x20 | 0x10 | 0x04 | 0x02
FULL = ANSWERED | 0x08
OPTIONS = {"test_option": "on"}


@pytest.fixture(scope="module")
def core(tmp_path_factory):
    built = tmp_path_factory.mktemp("core") / f"testcore{SUFFIX}"
    subprocess.run(["cc", "-shared", "-fPIC", "-O1", "-o", str(built), str(FIXTURE)], check=True)
    return built


@pytest.fixture
def content(tmp_path):
    path = tmp_path / "content.bin"
    path.write_bytes(bytes([SEED, 1, 2, 3]))
    return path


@pytest.mark.cc
class TestCapturingFrames:
    def test_every_frame_arrives_at_the_cores_size(self, core, content, tmp_path):
        # Arrange
        frames = 4

        # Act
        captured = libretro.capture(
            core, content, frames=frames, system_dir=tmp_path, options=OPTIONS
        )

        # Assert
        assert [(index, frame.shape) for index, frame in captured] == [
            (0, (2, 4, 3)),
            (1, (2, 4, 3)),
            (2, (2, 4, 3)),
            (3, (2, 4, 3)),
        ]

    def test_the_pixels_are_the_ones_the_core_drew(self, core, content, tmp_path):
        # Arrange
        frames = 1

        # Act
        [(_, first)] = libretro.capture(
            core, content, frames=frames, system_dir=tmp_path, options=OPTIONS
        )

        # Assert
        assert first[1].tolist() == [
            [SEED, 1, FULL],
            [SEED, 17, FULL],
            [SEED, 33, FULL],
            [SEED, 49, FULL],
        ]

    def test_a_duplicated_frame_repeats_the_last_picture(self, core, content, tmp_path):
        # Arrange
        frames = 3

        # Act
        captured = libretro.capture(
            core, content, frames=frames, system_dir=tmp_path, options=OPTIONS
        )

        # Assert
        assert np.array_equal(captured[2][1], captured[1][1])

    def test_only_the_kept_frames_are_returned(self, core, content, tmp_path):
        # Arrange
        keep = frozenset({1, 4})

        # Act
        captured = libretro.capture(core, content, frames=6, system_dir=tmp_path, keep=keep)

        # Assert
        assert [(index, int(frame[0, 0, 0])) for index, frame in captured] == [
            (1, SEED + 1),
            (4, SEED + 4),
        ]

    def test_content_the_core_refuses_is_reported(self, core, tmp_path):
        # Arrange
        empty = tmp_path / "empty.bin"
        empty.write_bytes(b"")

        # Act
        with pytest.raises(RuntimeError) as refused:
            libretro.capture(core, empty, frames=1, system_dir=tmp_path)

        # Assert
        assert str(refused.value) == f"{core.name} refused {empty}"


class TestRefusals:
    def test_a_missing_core_is_named(self, tmp_path):
        # Arrange
        absent = tmp_path / "absent.dylib"

        # Act
        with pytest.raises(FileNotFoundError) as refused:
            libretro.capture(absent, tmp_path, frames=1, system_dir=tmp_path)

        # Assert
        assert str(refused.value) == f"no libretro core at {absent}"

    def test_missing_content_is_named(self, tmp_path):
        # Arrange
        core = tmp_path / "core.dylib"
        core.write_bytes(b"")
        absent = tmp_path / "absent.neo"

        # Act
        with pytest.raises(FileNotFoundError) as refused:
            libretro.capture(core, absent, frames=1, system_dir=tmp_path)

        # Assert
        assert str(refused.value) == f"no content at {absent}"

    def test_a_run_of_no_frames_is_refused(self, tmp_path):
        # Arrange
        frames = 0

        # Act
        with pytest.raises(ValueError) as refused:
            libretro.capture(tmp_path, tmp_path, frames=frames, system_dir=tmp_path)

        # Assert
        assert str(refused.value) == "a run needs at least one frame, got 0"


class TestPixelFormats:
    def test_rgb565_widens_each_channel_to_eight_bits(self):
        # Arrange
        raw = np.array([[0xF800, 0x07E0, 0x001F, 0xFFFF]], dtype="<u2").tobytes()

        # Act
        rgb = libretro.to_rgb(raw, width=4, height=1, pitch=8, pixel_format=libretro.RGB565)

        # Assert
        assert rgb[0].tolist() == [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 255]]

    def test_0rgb1555_widens_each_channel_to_eight_bits(self):
        # Arrange
        raw = np.array([[0x7C00, 0x03E0, 0x001F, 0x0000]], dtype="<u2").tobytes()

        # Act
        rgb = libretro.to_rgb(raw, width=4, height=1, pitch=8, pixel_format=libretro.RGB1555)

        # Assert
        assert rgb[0].tolist() == [[255, 0, 0], [0, 255, 0], [0, 0, 255], [0, 0, 0]]

    def test_xrgb8888_reads_past_the_row_padding(self):
        # Arrange
        raw = np.array([0x00102030, 0xDEADBEEF, 0x00405060, 0xDEADBEEF], dtype="<u4").tobytes()

        # Act
        rgb = libretro.to_rgb(raw, width=1, height=2, pitch=8, pixel_format=libretro.XRGB8888)

        # Assert
        assert rgb[:, 0].tolist() == [[0x10, 0x20, 0x30], [0x40, 0x50, 0x60]]

    def test_an_unknown_format_is_refused(self):
        # Arrange
        raw = bytes(4)

        # Act
        with pytest.raises(ValueError) as refused:
            libretro.to_rgb(raw, width=1, height=1, pitch=4, pixel_format=7)

        # Assert
        assert str(refused.value) == "pixel format 7 is not one libretro defines"


@pytest.mark.cc
class TestCoreOptions:
    def test_an_option_the_caller_does_not_set_is_left_to_the_core(self, core, content, tmp_path):
        # Arrange
        options = {"another_option": "on"}

        # Act
        [(_, first)] = libretro.capture(
            core, content, frames=1, system_dir=tmp_path, options=options
        )

        # Assert
        assert int(first[0, 0, 2]) == ANSWERED


class TestDeclaredOptions:
    def test_a_list_that_never_ends_is_refused(self):
        # Arrange
        endless = (libretro.Variable * (libretro.MAX_VARIABLES + 1))(
            *[libretro.Variable(b"key", b"Key; a|b")] * (libretro.MAX_VARIABLES + 1)
        )

        # Act
        with pytest.raises(ValueError) as refused:
            libretro._declared(ctypes.addressof(endless))

        # Assert
        assert str(refused.value) == (
            f"a core declared more than {libretro.MAX_VARIABLES} options without ending the list"
        )
