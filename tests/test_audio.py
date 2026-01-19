"""Tests for trackid.audio module."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from trackid.audio import (
    get_duration,
    download_audio,
    extract_segment,
    chop_into_chunks,
    calculate_chunk_boundaries,
    get_total_duration_for_chunks,
    DownloadError,
    ProcessingError,
)


class TestGetDuration:
    """Tests for get_duration function."""

    @patch("trackid.audio.subprocess.run")
    def test_returns_duration(self, mock_run, temp_audio_dir):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="123.45\n",
            stderr="",
        )

        audio_file = temp_audio_dir / "test.mp3"
        audio_file.touch()

        duration = get_duration(audio_file)

        assert duration == 123.45
        mock_run.assert_called_once()

    @patch("trackid.audio.subprocess.run")
    def test_raises_on_ffprobe_failure(self, mock_run, temp_audio_dir):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error",
        )

        audio_file = temp_audio_dir / "test.mp3"
        audio_file.touch()

        with pytest.raises(ProcessingError):
            get_duration(audio_file)

    @patch("trackid.audio.subprocess.run")
    def test_raises_on_invalid_output(self, mock_run, temp_audio_dir):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not a number\n",
            stderr="",
        )

        audio_file = temp_audio_dir / "test.mp3"
        audio_file.touch()

        with pytest.raises(ProcessingError):
            get_duration(audio_file)


class TestDownloadAudio:
    """Tests for download_audio function."""

    @patch("trackid.audio.subprocess.run")
    def test_basic_download(self, mock_run, temp_audio_dir):
        output_path = temp_audio_dir / "output.mp3"

        # Simulate yt-dlp creating the file
        def create_file(*args, **kwargs):
            output_path.write_bytes(b"fake audio data")
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = create_file

        result = download_audio("https://example.com/audio", output_path)

        assert result == output_path
        assert result.exists()
        mock_run.assert_called_once()

    @patch("trackid.audio.subprocess.run")
    def test_download_with_time_range(self, mock_run, temp_audio_dir):
        output_path = temp_audio_dir / "output.mp3"

        def create_file(*args, **kwargs):
            output_path.write_bytes(b"fake audio data")
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = create_file

        download_audio(
            "https://example.com/audio",
            output_path,
            start_seconds=60,
            end_seconds=120,
        )

        # Check that --download-sections was included
        call_args = mock_run.call_args[0][0]
        assert "--download-sections" in call_args

    @patch("trackid.audio.subprocess.run")
    def test_raises_on_failure(self, mock_run, temp_audio_dir):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Download error",
        )

        output_path = temp_audio_dir / "output.mp3"

        with pytest.raises(DownloadError):
            download_audio("https://example.com/audio", output_path)


class TestExtractSegment:
    """Tests for extract_segment function."""

    @patch("trackid.audio.subprocess.run")
    def test_extracts_segment(self, mock_run, temp_audio_dir):
        input_path = temp_audio_dir / "input.mp3"
        input_path.write_bytes(b"fake input")
        output_path = temp_audio_dir / "output.mp3"

        def create_file(*args, **kwargs):
            output_path.write_bytes(b"fake output")
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = create_file

        result = extract_segment(input_path, output_path, 30, 20)

        assert result == output_path
        assert result.exists()

        # Check ffmpeg was called with correct arguments
        call_args = mock_run.call_args[0][0]
        assert "-ss" in call_args
        assert "30" in call_args
        assert "-t" in call_args
        assert "20" in call_args

    @patch("trackid.audio.subprocess.run")
    def test_raises_on_failure(self, mock_run, temp_audio_dir):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="ffmpeg error",
        )

        input_path = temp_audio_dir / "input.mp3"
        input_path.write_bytes(b"fake input")
        output_path = temp_audio_dir / "output.mp3"

        with pytest.raises(ProcessingError):
            extract_segment(input_path, output_path, 30, 20)


class TestChopIntoChunks:
    """Tests for chop_into_chunks function."""

    @patch("trackid.audio.extract_segment")
    @patch("trackid.audio.get_duration")
    def test_creates_correct_number_of_chunks(
        self, mock_duration, mock_extract, temp_audio_dir
    ):
        mock_duration.return_value = 65.0  # 65 seconds

        input_path = temp_audio_dir / "input.mp3"
        input_path.write_bytes(b"fake input")
        chunks_dir = temp_audio_dir / "chunks"

        # Mock extract_segment to create files
        def create_chunk(audio, output, start, duration):
            output.write_bytes(b"chunk")
            return output

        mock_extract.side_effect = create_chunk

        chunks = chop_into_chunks(input_path, chunks_dir, chunk_duration=20)

        # 65 seconds / 20 = 3 chunks + remainder (5s < 5, so no extra chunk)
        assert len(chunks) == 3

        # Check chunk metadata
        assert chunks[0][0] == 0  # First chunk index
        assert chunks[0][1] == 0  # First chunk start time
        assert chunks[1][1] == 20  # Second chunk start time
        assert chunks[2][1] == 40  # Third chunk start time

    @patch("trackid.audio.extract_segment")
    @patch("trackid.audio.get_duration")
    def test_adds_extra_chunk_for_significant_remainder(
        self, mock_duration, mock_extract, temp_audio_dir
    ):
        mock_duration.return_value = 66.0  # 66 seconds (6s remainder > 5)

        input_path = temp_audio_dir / "input.mp3"
        input_path.write_bytes(b"fake input")
        chunks_dir = temp_audio_dir / "chunks"

        def create_chunk(audio, output, start, duration):
            output.write_bytes(b"chunk")
            return output

        mock_extract.side_effect = create_chunk

        chunks = chop_into_chunks(input_path, chunks_dir, chunk_duration=20)

        # 66 seconds / 20 = 3 chunks + 1 for remainder (6s > 5)
        assert len(chunks) == 4


class TestCalculateChunkBoundaries:
    """Tests for calculate_chunk_boundaries function."""

    def test_single_chunk(self):
        # 1 chunk at timestamp 100: should cover 90-120 (30 seconds)
        boundaries = calculate_chunk_boundaries(100, 1)

        assert len(boundaries) == 1
        assert boundaries[0] == (90, 120)

    def test_two_chunks(self):
        # 2 chunks at timestamp 100: 90-120, then 120-140
        boundaries = calculate_chunk_boundaries(100, 2)

        assert len(boundaries) == 2
        assert boundaries[0] == (90, 120)
        assert boundaries[1] == (120, 140)

    def test_five_chunks(self):
        # 5 chunks at timestamp 100
        boundaries = calculate_chunk_boundaries(100, 5)

        assert len(boundaries) == 5
        assert boundaries[0] == (90, 120)   # -10 to +20
        assert boundaries[1] == (120, 140)  # +20 to +40
        assert boundaries[2] == (140, 160)  # +40 to +60
        assert boundaries[3] == (160, 180)  # +60 to +80
        assert boundaries[4] == (180, 200)  # +80 to +100

    def test_clamps_to_zero(self):
        # Timestamp at 5s, chunk should start at 0
        boundaries = calculate_chunk_boundaries(5, 1)

        assert boundaries[0][0] == 0  # Start clamped to 0
        assert boundaries[0][1] == 25  # End at timestamp + 20

    def test_clamps_num_chunks(self):
        # Should clamp to max 5 chunks
        boundaries = calculate_chunk_boundaries(100, 10)
        assert len(boundaries) == 5

        # Should clamp to min 1 chunk
        boundaries = calculate_chunk_boundaries(100, 0)
        assert len(boundaries) == 1


class TestGetTotalDurationForChunks:
    """Tests for get_total_duration_for_chunks function."""

    def test_single_chunk(self):
        start, end = get_total_duration_for_chunks(100, 1)

        assert start == 90   # timestamp - 10
        assert end == 120    # timestamp + 20

    def test_three_chunks(self):
        start, end = get_total_duration_for_chunks(100, 3)

        assert start == 90   # timestamp - 10
        assert end == 160    # timestamp + 60

    def test_five_chunks(self):
        start, end = get_total_duration_for_chunks(100, 5)

        assert start == 90   # timestamp - 10
        assert end == 200    # timestamp + 100

    def test_timestamp_near_zero(self):
        start, end = get_total_duration_for_chunks(5, 1)

        assert start == 0    # Clamped to 0
        assert end == 25     # 5 + 20
