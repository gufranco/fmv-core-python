from __future__ import annotations

import hashlib

import numpy as np
import pytest

from fmvcore import fixture

SIZE_LIMIT = 128 * 1024


class TestTheCommittedClip:
    def test_it_is_in_the_repository(self):
        # Arrange
        target = fixture.FIXTURE

        # Act
        exists = target.is_file()

        # Assert
        assert exists is True

    def test_it_is_small_enough_to_carry(self):
        # Arrange
        target = fixture.FIXTURE

        # Act
        size = target.stat().st_size

        # Assert
        assert size < SIZE_LIMIT


class TestTheFrames:
    def test_a_frame_has_the_clips_size(self):
        # Arrange
        base, grid = fixture.block_field()

        # Act
        frame = fixture.frame_at(0, base, grid)

        # Assert
        assert frame.shape == (fixture.HEIGHT, fixture.WIDTH, 3)

    def test_the_same_index_gives_the_same_frame(self):
        # Arrange
        base, grid = fixture.block_field()
        first = fixture.frame_at(5, base, grid)

        # Act
        second = fixture.frame_at(5, base, grid)

        # Assert
        assert np.array_equal(first, second) is True

    def test_successive_frames_differ(self):
        # Arrange
        base, grid = fixture.block_field()
        first = fixture.frame_at(0, base, grid)

        # Act
        second = fixture.frame_at(1, base, grid)

        # Assert
        assert np.array_equal(first, second) is False

    def test_no_eight_by_eight_cell_is_flat(self):
        # Arrange
        base, grid = fixture.block_field()

        # Act
        frame = fixture.frame_at(3, base, grid)

        # Assert
        cells = frame.reshape(fixture.HEIGHT // 8, 8, fixture.WIDTH // 8, 8, 3)
        flat = cells.transpose(0, 2, 1, 3, 4).reshape(-1, 64, 3)
        assert bool(np.any(flat.min(axis=1) == flat.max(axis=1))) is False

    def test_the_frame_uses_nearly_the_whole_range(self):
        # Arrange
        base, grid = fixture.block_field()

        # Act
        frame = fixture.frame_at(7, base, grid)

        # Assert
        assert (int(frame.min()) < 40, int(frame.max()) > 215) == (True, True)


@pytest.mark.ffmpeg
class TestTheClipIsReproducible:
    def test_two_builds_write_the_same_bytes(self, tmp_path):
        # Arrange
        first = fixture.build(tmp_path / "first.mp4")

        # Act
        second = fixture.build(tmp_path / "second.mp4")

        # Assert
        assert (
            hashlib.sha256(first.read_bytes()).digest()
            == hashlib.sha256(second.read_bytes()).digest()
        )

    def test_the_command_reports_where_it_wrote(self, tmp_path, capsys):
        # Arrange
        target = tmp_path / "fixture.mp4"

        # Act
        code = fixture.main([str(target)])

        # Assert
        assert (code, f"wrote {target}" in capsys.readouterr().out) == (0, True)


class TestAFailingEncoder:
    def test_its_exit_code_is_reported(self, tmp_path):
        # Arrange
        failing = ("sh", "-c", "cat >/dev/null; exit 3")

        # Act
        with pytest.raises(RuntimeError) as refused:
            fixture.build(tmp_path / "broken.mp4", command=failing)

        # Assert
        assert str(refused.value) == "ffmpeg exited 3"
