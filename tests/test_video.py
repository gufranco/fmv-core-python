import subprocess
from dataclasses import replace
from fractions import Fraction

import numpy as np
import pytest

from fmvcore import video

pytestmark = pytest.mark.ffmpeg

NTSC_FIELDS = Fraction(3_579_545, 262 * 228)
NEO_GEO_FIELDS = Fraction(6_000_000, 384 * 264)
MASTER_SYSTEM = video.Picture(width=256, height=192, rate=NTSC_FIELDS)
NEO_GEO = video.Picture(width=320, height=224, rate=NEO_GEO_FIELDS)
SMALL = video.Picture(width=32, height=24, rate=NTSC_FIELDS)
FRAMES = 6
SEED = 20261102


def console_frames(picture, count=FRAMES):
    generator = np.random.default_rng(SEED)
    levels = np.array([0, 85, 170, 255], dtype=np.uint8)
    cells = generator.integers(0, len(levels), size=(count, picture.height, picture.width, 3))
    return list(levels[cells])


def encode(path, picture, frames):
    command = video.writer_command(path, picture)
    subprocess.run(command, input=np.stack(frames).tobytes(), check=True)


class TestEnlargement:
    def test_a_master_system_picture_takes_eight_times(self):
        # Arrange
        picture = MASTER_SYSTEM

        # Act
        factor = video.enlargement(picture)

        # Assert
        assert factor == 8

    def test_a_neo_geo_picture_takes_the_largest_even_factor_level_five_one_holds(self):
        # Arrange
        picture = NEO_GEO

        # Act
        factor = video.enlargement(picture)

        # Assert
        assert factor == 6

    def test_a_picture_too_large_for_the_level_is_refused(self):
        # Arrange
        picture = video.Picture(width=8192, height=8192, rate=NTSC_FIELDS)

        # Act
        with pytest.raises(ValueError) as refused:
            video.enlargement(picture)

        # Assert
        assert "level 5.1" in str(refused.value)


class TestNearLosslessVideo:
    def test_the_decoded_frames_stay_within_five_levels(self, tmp_path):
        # Arrange
        path = tmp_path / "preview.mp4"
        frames = console_frames(SMALL)
        encode(path, SMALL, frames)

        # Act
        checked = video.check(path, SMALL, frames)

        # Assert
        assert checked is None

    def test_random_colours_at_the_neo_geo_enlargement_stay_within_seven_levels(self, tmp_path):
        # Arrange
        path = tmp_path / "neo.mp4"
        generator = np.random.default_rng(SEED)
        frames = list(generator.integers(0, 256, size=(2, 224, 320, 3), dtype=np.uint8))
        picture = replace(NEO_GEO, most_drift=7)
        encode(path, picture, frames)

        # Act
        checked = video.check(path, picture, frames)

        # Assert
        assert checked is None

    def test_a_crf_encode_is_refused(self, tmp_path):
        # Arrange
        path = tmp_path / "blurred.mp4"
        frames = console_frames(SMALL)
        command = video.writer_command(path, SMALL)
        blurred = [*command[: command.index("-vf")], "-c:v", "libx264", "-crf", "30", str(path)]
        subprocess.run(blurred, input=np.stack(frames).tobytes(), check=True)

        # Act
        with pytest.raises(ValueError) as refused:
            video.check(path, SMALL, frames)

        # Assert
        assert "every player opens" in str(refused.value)

    def test_frames_that_drift_are_refused(self, tmp_path):
        # Arrange
        path = tmp_path / "preview.mp4"
        frames = console_frames(SMALL)
        encode(path, SMALL, frames)
        moved = [255 - frame for frame in frames]

        # Act
        with pytest.raises(ValueError) as refused:
            video.check(path, SMALL, moved)

        # Assert
        assert "drifts" in str(refused.value)

    def test_a_file_with_no_picture_is_refused(self, tmp_path):
        # Arrange
        path = tmp_path / "silent.mp4"
        command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc", "-t", "0.1", str(path)]
        subprocess.run(command, check=True)

        # Act
        with pytest.raises(ValueError) as refused:
            video.check(path, SMALL, [])

        # Assert
        assert "'level': None" in str(refused.value)


class TestLosslessVideo:
    def test_a_matroska_file_is_lossless_at_the_console_size(self, tmp_path):
        # Arrange
        path = tmp_path / "preview.mkv"

        # Act
        command = video.writer_command(path, SMALL)

        # Assert
        assert command[-len(video.LOSSLESS) - 1 : -1] == list(video.LOSSLESS)

    def test_a_lossless_file_needs_no_check(self, tmp_path):
        # Arrange
        path = tmp_path / "preview.mkv"

        # Act
        checked = video.check(path, SMALL, [])

        # Assert
        assert checked is None
