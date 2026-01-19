"""Audio processing functions using ffmpeg and yt-dlp."""

import subprocess
from pathlib import Path

from .config import settings
from .utils import format_time_padded, get_base_name


class AudioError(Exception):
    """Base exception for audio processing errors."""

    pass


class DownloadError(AudioError):
    """Error downloading audio."""

    pass


class ProcessingError(AudioError):
    """Error processing audio with ffmpeg."""

    pass


def get_duration(audio_path: Path) -> float:
    """Get the duration of an audio file in seconds.

    Args:
        audio_path: Path to the audio file.

    Returns:
        Duration in seconds.

    Raises:
        ProcessingError: If ffprobe fails.
    """
    try:
        result = subprocess.run(
            [
                settings.ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise ProcessingError(f"ffprobe failed: {result.stderr}")

        return float(result.stdout.strip())

    except subprocess.TimeoutExpired:
        raise ProcessingError("ffprobe timed out")
    except ValueError as e:
        raise ProcessingError(f"Could not parse duration: {e}")


def download_audio(
    url: str,
    output_path: Path,
    start_seconds: int | None = None,
    end_seconds: int | None = None,
    timeout: int = 300,
) -> Path:
    """Download audio from a URL using yt-dlp.

    Args:
        url: The URL to download from.
        output_path: Where to save the downloaded file.
        start_seconds: Start time in seconds (optional).
        end_seconds: End time in seconds (optional).
        timeout: Download timeout in seconds.

    Returns:
        Path to the downloaded file.

    Raises:
        DownloadError: If the download fails.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build yt-dlp command
    cmd = [
        settings.ytdlp_path,
        "-x",  # Extract audio
        "--audio-format",
        "mp3",
        "--audio-quality",
        "128K",
        "-o",
        str(output_path.with_suffix(".%(ext)s")),
        "--no-playlist",
        "--socket-timeout",
        "30",
    ]

    # Add time range if specified
    if start_seconds is not None or end_seconds is not None:
        start = start_seconds or 0
        end = end_seconds or 999999  # Large number for "until end"
        start_ts = format_time_padded(start)
        end_ts = format_time_padded(end)
        cmd.extend(["--download-sections", f"*{start_ts}-{end_ts}"])

    cmd.append(url)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # yt-dlp might create file with different extension, find it
        output_mp3 = output_path.with_suffix(".mp3")

        # Check for various possible output files
        for ext in [".mp3", ".m4a", ".opus", ".webm", ".mp3.mp3"]:
            potential = output_path.with_suffix(ext)
            if potential.exists() and potential.stat().st_size > 0:
                # Convert to mp3 if needed
                if ext != ".mp3":
                    convert_to_mp3(potential, output_mp3)
                    potential.unlink()
                elif potential != output_mp3:
                    potential.rename(output_mp3)
                return output_mp3

        # Also check for files matching the stem
        for f in output_path.parent.glob(f"{output_path.stem}*"):
            if f.stat().st_size > 0:
                if f.suffix != ".mp3":
                    convert_to_mp3(f, output_mp3)
                    f.unlink()
                elif f != output_mp3:
                    f.rename(output_mp3)
                return output_mp3

        error_msg = result.stderr[:500] if result.stderr else "Unknown error"
        raise DownloadError(f"Download failed: {error_msg}")

    except subprocess.TimeoutExpired:
        raise DownloadError(f"Download timed out after {timeout} seconds")


def convert_to_mp3(input_path: Path, output_path: Path, timeout: int = 120) -> Path:
    """Convert an audio file to MP3 using ffmpeg.

    Args:
        input_path: Path to the input file.
        output_path: Path for the output MP3 file.
        timeout: Conversion timeout in seconds.

    Returns:
        Path to the converted file.

    Raises:
        ProcessingError: If conversion fails.
    """
    try:
        result = subprocess.run(
            [
                settings.ffmpeg_path,
                "-i",
                str(input_path),
                "-acodec",
                "libmp3lame",
                "-ab",
                "128k",
                "-y",
                "-loglevel",
                "error",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0 or not output_path.exists():
            raise ProcessingError(f"Conversion failed: {result.stderr}")

        return output_path

    except subprocess.TimeoutExpired:
        raise ProcessingError("Conversion timed out")


def extract_segment(
    audio_path: Path,
    output_path: Path,
    start_seconds: int,
    duration_seconds: int,
    timeout: int = 60,
) -> Path:
    """Extract a segment from an audio file.

    Args:
        audio_path: Path to the source audio file.
        output_path: Path for the extracted segment.
        start_seconds: Start time in seconds.
        duration_seconds: Duration of the segment in seconds.
        timeout: Extraction timeout in seconds.

    Returns:
        Path to the extracted segment.

    Raises:
        ProcessingError: If extraction fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                settings.ffmpeg_path,
                "-ss",
                str(start_seconds),
                "-i",
                str(audio_path),
                "-t",
                str(duration_seconds),
                "-acodec",
                "libmp3lame",
                "-ab",
                "128k",
                "-y",
                "-loglevel",
                "error",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0 or not output_path.exists():
            raise ProcessingError(f"Segment extraction failed: {result.stderr}")

        return output_path

    except subprocess.TimeoutExpired:
        raise ProcessingError("Segment extraction timed out")


def chop_into_chunks(
    audio_path: Path,
    output_dir: Path,
    chunk_duration: int = 20,
) -> list[tuple[int, int, Path]]:
    """Split an audio file into chunks.

    Args:
        audio_path: Path to the source audio file.
        output_dir: Directory to save chunks.
        chunk_duration: Duration of each chunk in seconds.

    Returns:
        List of tuples (chunk_index, start_seconds, chunk_path).

    Raises:
        ProcessingError: If chunking fails.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get total duration
    total_duration = get_duration(audio_path)
    num_chunks = max(1, int(total_duration // chunk_duration))

    # Add one more chunk if there's significant remainder
    if total_duration % chunk_duration > 5:
        num_chunks += 1

    chunks = []
    base_name = audio_path.stem

    for i in range(num_chunks):
        start = i * chunk_duration
        chunk_path = output_dir / f"{base_name}_chunk{i:03d}.mp3"

        if not chunk_path.exists():
            extract_segment(audio_path, chunk_path, start, chunk_duration)

        if chunk_path.exists() and chunk_path.stat().st_size > 0:
            chunks.append((i, start, chunk_path))

    return chunks


def calculate_chunk_boundaries(
    timestamp: int,
    num_chunks: int,
) -> list[tuple[int, int]]:
    """Calculate chunk boundaries for identification.

    Chunk 0 covers timestamp-10 to timestamp+20 (30s centered on timestamp).
    Each additional chunk extends 20s further.

    Args:
        timestamp: The timestamp to identify (in seconds).
        num_chunks: Number of chunks (1-5).

    Returns:
        List of (start_seconds, end_seconds) tuples for each chunk.
    """
    num_chunks = max(1, min(5, num_chunks))  # Clamp to 1-5

    boundaries = []

    # Chunk 0: -10s to +20s (30s, centered on timestamp)
    chunk0_start = max(0, timestamp - 10)
    chunk0_end = timestamp + 20
    boundaries.append((chunk0_start, chunk0_end))

    # Additional chunks: each adds 20s
    for i in range(1, num_chunks):
        start = timestamp + 20 + (i - 1) * 20
        end = start + 20
        boundaries.append((start, end))

    return boundaries


def get_total_duration_for_chunks(timestamp: int, num_chunks: int) -> tuple[int, int]:
    """Get the total time range needed for the given number of chunks.

    Args:
        timestamp: The timestamp to identify (in seconds).
        num_chunks: Number of chunks (1-5).

    Returns:
        Tuple of (start_seconds, end_seconds) covering all chunks.
    """
    boundaries = calculate_chunk_boundaries(timestamp, num_chunks)
    start = boundaries[0][0]
    end = boundaries[-1][1]
    return (start, end)


def download_and_prepare(
    url: str,
    output_dir: Path,
    start_seconds: int | None = None,
    end_seconds: int | None = None,
    chunk_duration: int | None = None,
) -> list[Path]:
    """Download audio and optionally chunk it.

    This is a convenience function that combines download and chunking.

    Args:
        url: The URL to download from.
        output_dir: Directory to save files.
        start_seconds: Start time in seconds (optional).
        end_seconds: End time in seconds (optional).
        chunk_duration: If provided, split into chunks of this duration.

    Returns:
        List of paths to audio files (either single file or chunks).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    base = get_base_name(url)
    if start_seconds is not None:
        base = f"{base}_{start_seconds}s"

    output_path = output_dir / f"{base}.mp3"

    # Download
    downloaded = download_audio(url, output_path, start_seconds, end_seconds)

    # Chunk if requested
    if chunk_duration:
        chunks_dir = output_dir / "chunks"
        chunk_list = chop_into_chunks(downloaded, chunks_dir, chunk_duration)
        return [path for _, _, path in chunk_list]

    return [downloaded]
