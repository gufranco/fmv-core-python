from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from fmvcore import fixture, source

WIDTH = 320
HEIGHT = 240
BAR = 60
WEAVE = ("tinterlace=mode=interleave_top", "setfield=tff")
INTERLACED_OUTPUT = ("-flags", "+ilme+ildct", "-x264opts", "tff=1")


def generated(path: Path, *filters: str) -> Path:
    chain = ",".join(["testsrc2=size=320x240:rate=25:duration=2", *filters])
    command = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", chain]
    subprocess.run([*command, "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def woven(path: Path) -> Path:
    command = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(fixture.FIXTURE)]
    filters = ["-vf", ",".join(WEAVE), "-pix_fmt", "yuv420p", *INTERLACED_OUTPUT]
    subprocess.run([*command, *filters, str(path)], check=True)
    return path


@pytest.mark.ffmpeg
class TestBars:
    def test_bars_baked_into_the_picture_are_found(self, tmp_path):
        # Arrange
        clip = generated(
            tmp_path / "boxed.mp4",
            f"scale={WIDTH}:{HEIGHT - 2 * BAR}",
            f"pad={WIDTH}:{HEIGHT}:0:{BAR}:black",
        )

        # Act
        found = source.analyse(clip, start=0.0, duration=2.0)

        # Assert
        assert found.crop == (WIDTH, HEIGHT - 2 * BAR, 0, BAR)

    def test_a_picture_with_no_bars_needs_no_crop(self, tmp_path):
        # Arrange
        clip = generated(tmp_path / "full.mp4")

        # Act
        found = source.analyse(clip, start=0.0, duration=2.0)

        # Assert
        assert found.crop is None


@pytest.mark.ffmpeg
class TestInterlacing:
    def test_a_progressive_source_is_not_called_interlaced(self):
        # Arrange
        clip = fixture.FIXTURE

        # Act
        found = source.analyse(clip, start=0.0, duration=2.0)

        # Assert
        assert found.interlaced is False

    def test_a_woven_source_is_called_interlaced(self, tmp_path):
        # Arrange
        clip = woven(tmp_path / "woven.mp4")

        # Act
        found = source.analyse(clip, start=0.0, duration=2.0)

        # Assert
        assert found.interlaced is True


class TestReports:
    def test_a_report_with_no_summary_reads_progressive(self):
        # Arrange
        report = "no detection here"

        # Act
        interlaced = source._interlaced(report)

        # Assert
        assert interlaced is False

    def test_a_report_with_no_crop_line_needs_no_crop(self, tmp_path):
        # Arrange
        report = "nothing to crop"

        # Act
        crop = source._crop(tmp_path / "unused.mp4", report)

        # Assert
        assert crop is None
