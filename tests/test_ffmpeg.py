import subprocess
import sys
from pathlib import Path

import pytest

from fmvcore import ffmpeg
from fmvcore.testing import seeded

FAKE = seeded()
FILM = FAKE.file_name(extension="mp4")

SHAPE = (2, 2, 3)
STRIDE = 12
CEILING = 100
PIPE_BUFFER_OVERRUN = 1 << 20
VIDEO = {"width": 320, "height": 240, "r_frame_rate": "30000/1001"}


def writer(*, stdout: int, stderr: int = 0, code: int = 0) -> list[str]:
    script = (
        "import sys\n"
        f"sys.stderr.write('e' * {stderr})\n"
        "sys.stderr.flush()\n"
        f"sys.stdout.buffer.write(bytes(i % 256 for i in range({stdout})))\n"
        f"sys.exit({code})\n"
    )
    return [sys.executable, "-I", "-c", script]


def streamed(command: list[str], *, max_frames: int = CEILING) -> list[object]:
    return list(ffmpeg.stream_frames(command, path=Path(FILM), shape=SHAPE, max_frames=max_frames))


def probed(*, streams: list[dict[str, object]], duration: object = "4.0") -> dict[str, object]:
    return {"streams": streams, "format": {"duration": duration}}


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    path = tmp_path_factory.mktemp("clip") / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=30:duration=2",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    return path


class TestTheDecodePipe:
    def test_whole_frames_arrive_in_order(self):
        # Arrange
        command = writer(stdout=STRIDE * 3)

        # Act
        decoded = streamed(command)

        # Assert
        assert len(decoded) == 3
        assert decoded[0].reshape(-1).tolist() == list(range(STRIDE))

    def test_a_decoder_that_fills_its_error_pipe_does_not_hang(self):
        # Arrange
        command = writer(stdout=STRIDE * 2, stderr=PIPE_BUFFER_OVERRUN)

        # Act
        decoded = streamed(command)

        # Assert
        assert len(decoded) == 2

    def test_a_partial_trailing_frame_is_refused(self):
        # Arrange
        command = writer(stdout=STRIDE * 2 + 5)

        # Act
        with pytest.raises(RuntimeError) as refused:
            streamed(command)

        # Assert
        assert str(refused.value) == (
            f"ffmpeg ended {FILM} on a partial frame of 5 bytes; a frame is 12"
        )

    def test_a_failed_decoder_is_reported_with_what_it_said(self):
        # Arrange
        command = writer(stdout=STRIDE, stderr=3, code=1)

        # Act
        with pytest.raises(RuntimeError) as refused:
            streamed(command)

        # Assert
        assert str(refused.value) == f"ffmpeg failed decoding {FILM} with exit code 1: eee"

    def test_a_decoder_past_the_frame_ceiling_is_stopped(self):
        # Arrange
        command = writer(stdout=STRIDE * 3)

        # Act
        with pytest.raises(RuntimeError) as refused:
            streamed(command, max_frames=2)

        # Assert
        assert str(refused.value) == f"{FILM} decoded past 2 frames"


class TestTheFrameCommand:
    def test_a_whole_source_is_read_from_its_start(self, monkeypatch):
        # Arrange
        monkeypatch.setattr(ffmpeg.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

        # Act
        command = ffmpeg.frame_command(
            Path(FILM), start=0.0, duration=None, stages=["fps=5", "crop=8:8"]
        )

        # Assert
        assert command == [
            "/usr/bin/ffmpeg",
            "-v",
            "error",
            "-i",
            FILM,
            "-vf",
            "fps=5,crop=8:8",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ]

    def test_a_window_seeks_before_the_input_and_limits_after_it(self, monkeypatch):
        # Arrange
        monkeypatch.setattr(ffmpeg.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

        # Act
        command = ffmpeg.frame_command(Path(FILM), start=1.5, duration=2.0, stages=["fps=5"])

        # Assert
        assert command[3:9] == ["-ss", "1.5", "-i", FILM, "-t", "2.0"]


@pytest.mark.ffmpeg
class TestDecodingARealFilm:
    def test_frames_arrive_at_the_requested_size(self, clip):
        # Arrange
        command = ffmpeg.frame_command(
            clip, start=0.0, duration=None, stages=["fps=5", "scale=16:8"]
        )

        # Act
        decoded = list(
            ffmpeg.stream_frames(command, path=clip, shape=(8, 16, 3), max_frames=CEILING)
        )

        # Assert
        assert len(decoded) == 10
        assert decoded[0].shape == (8, 16, 3)


class TestWhatTheProbeReports:
    def test_a_readable_source_is_described(self):
        # Arrange
        parsed = probed(streams=[VIDEO])

        # Act
        info = ffmpeg.source_info(parsed, path=Path(FILM))

        # Assert
        assert info == ffmpeg.SourceInfo(width=320, height=240, fps=30000 / 1001, duration=4.0)

    def test_a_source_with_no_video_stream_is_refused_by_name(self):
        # Arrange
        parsed = probed(streams=[])

        # Act
        with pytest.raises(ValueError) as refused:
            ffmpeg.source_info(parsed, path=Path("song.m4a"))

        # Assert
        assert str(refused.value) == "song.m4a has no video stream ffprobe can read"

    @pytest.mark.parametrize("rate", ["0/0", "0/1", "-30/1", "abc"])
    def test_an_unusable_frame_rate_is_refused(self, rate):
        # Arrange
        parsed = probed(streams=[{**VIDEO, "r_frame_rate": rate}])

        # Act
        with pytest.raises(ValueError) as refused:
            ffmpeg.source_info(parsed, path=Path(FILM))

        # Assert
        assert str(refused.value).startswith(f"{FILM} does not report a usable size")

    @pytest.mark.parametrize("duration", ["N/A", None, "0", "inf"])
    def test_an_unusable_duration_is_refused(self, duration):
        # Arrange
        parsed = probed(streams=[VIDEO], duration=duration)

        # Act
        with pytest.raises(ValueError) as refused:
            ffmpeg.source_info(parsed, path=Path(FILM))

        # Assert
        assert str(refused.value).startswith(f"{FILM} ")

    def test_a_missing_format_block_is_refused(self):
        # Arrange
        parsed = {"streams": [VIDEO]}

        # Act
        with pytest.raises(ValueError) as refused:
            ffmpeg.source_info(parsed, path=Path(FILM))

        # Assert
        assert str(refused.value).startswith(f"{FILM} does not report a usable size")


@pytest.mark.ffmpeg
class TestProbe:
    def test_it_reads_the_source_geometry(self, clip):
        # Arrange
        source = clip

        # Act
        result = ffmpeg.probe(source)

        # Assert
        assert (result.width, result.height) == (320, 240)

    def test_it_reads_the_duration(self, clip):
        # Arrange
        source = clip

        # Act
        result = ffmpeg.probe(source)

        # Assert
        assert result.duration == pytest.approx(2.0, abs=0.2)


class TestProbeRefusals:
    def test_a_missing_file_is_refused(self, tmp_path):
        # Arrange
        absent = tmp_path / "absent.mp4"

        # Act
        with pytest.raises(FileNotFoundError) as refused:
            ffmpeg.probe(absent)

        # Assert
        assert str(refused.value) == f"no such source file: {absent}"


class TestRequireTool:
    def test_an_absent_tool_is_named_plainly(self, monkeypatch):
        # Arrange
        monkeypatch.setattr(ffmpeg.shutil, "which", lambda _name: None)

        # Act
        with pytest.raises(RuntimeError) as refused:
            ffmpeg.require_tool("ffmpeg")

        # Assert
        assert str(refused.value) == "ffmpeg is not on the path, and the decode path needs it"

    def test_a_present_tool_resolves_to_its_path(self, monkeypatch):
        # Arrange
        monkeypatch.setattr(ffmpeg.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

        # Act
        resolved = ffmpeg.require_tool("ffmpeg")

        # Assert
        assert resolved == "/usr/bin/ffmpeg"


class TestScalerCheck:
    @pytest.mark.parametrize("scaler", ffmpeg.SCALERS)
    def test_every_named_scaler_is_accepted(self, scaler):
        # Arrange
        name = scaler

        # Act
        accepted = ffmpeg.check_scaler(name)

        # Assert
        assert accepted is None

    def test_an_unknown_scaler_is_refused_with_the_choices(self):
        # Arrange
        name = "nearest"

        # Act
        with pytest.raises(ValueError) as refused:
            ffmpeg.check_scaler(name)

        # Assert
        assert str(refused.value) == (
            "scaler 'nearest' is not one of area, bicubic, bilinear, fast_bilinear, gauss, "
            "lanczos, neighbor, sinc, spline"
        )
