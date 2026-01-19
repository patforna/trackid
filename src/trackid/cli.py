"""Command-line interface for trackid."""

import json
import shutil
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from . import __version__
from .audio import (
    AudioError,
    calculate_chunk_boundaries,
    download_audio,
    DownloadError,
    extract_segment,
    get_total_duration_for_chunks,
)
from .config import settings
from .identify import (
    TrackMatch,
    run_identify,
)
from .utils import format_time, is_url, parse_time, get_base_name

app = typer.Typer(
    name="trackid",
    help="Identify music tracks using Shazam and ACRCloud.",
    no_args_is_help=True,
)

# stderr for status/debug messages
err_console = Console(stderr=True)
# stdout for program output
out_console = Console()


class OutputFormat(str, Enum):
    """Output format options."""

    TABLE = "table"
    JSON = "json"
    PLAIN = "plain"


class ServiceChoice(str, Enum):
    """Service selection options."""

    SHAZAM = "shazam"
    ACRCLOUD = "acrcloud"
    ALL = "all"


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        out_console.print(f"trackid {__version__}")
        raise typer.Exit()


def print_match_table(match: TrackMatch) -> None:
    """Print a single match as formatted output."""
    out_console.print()
    out_console.print("[bold green]Track identified:[/bold green]")
    out_console.print()
    out_console.print(f"  [bold]Title:[/bold]   {match.title}")
    out_console.print(f"  [bold]Artist:[/bold]  {match.artist}")
    if match.album:
        out_console.print(f"  [bold]Album:[/bold]   {match.album}")
    out_console.print(f"  [bold]Service:[/bold] {match.service}")
    if match.url:
        out_console.print(f"  [bold]URL:[/bold]     {match.url}")
    out_console.print()


def print_match_json(match: TrackMatch | None) -> None:
    """Print match as JSON."""
    if match:
        data = {
            "title": match.title,
            "artist": match.artist,
            "album": match.album,
            "service": match.service,
            "url": match.url,
        }
    else:
        data = None
    out_console.print(json.dumps({"match": data}, indent=2))


def print_match_plain(match: TrackMatch | None) -> None:
    """Print match as plain text (artist - title)."""
    if match:
        out_console.print(f"{match.artist} - {match.title}")
    else:
        out_console.print("No match found")


def print_match(match: TrackMatch | None, output_format: OutputFormat) -> None:
    """Print match in the specified format."""
    if match is None:
        if output_format == OutputFormat.JSON:
            print_match_json(None)
        elif output_format == OutputFormat.PLAIN:
            print_match_plain(None)
        else:
            out_console.print("[yellow]No match found.[/yellow]")
        return

    if output_format == OutputFormat.TABLE:
        print_match_table(match)
    elif output_format == OutputFormat.JSON:
        print_match_json(match)
    elif output_format == OutputFormat.PLAIN:
        print_match_plain(match)


@app.command()
def identify(
    source: Annotated[
        str,
        typer.Argument(help="Audio file path or URL (SoundCloud, YouTube, etc.)"),
    ],
    time: Annotated[
        Optional[str],
        typer.Option("--time", "-t", help="Timestamp to identify (required for URLs, e.g., '7:45' or '1:23:45')"),
    ] = None,
    chunks: Annotated[
        int,
        typer.Option("--chunks", "-c", help="Number of chunks to try (1-5, default: 1)"),
    ] = 1,
    service: Annotated[
        ServiceChoice,
        typer.Option("--service", "-s", help="Identification service to use"),
    ] = ServiceChoice.ALL,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = OutputFormat.TABLE,
    keep_files: Annotated[
        bool,
        typer.Option("--keep-files", help="Keep downloaded audio files (default: False, files are deleted)"),
    ] = False,
    output_dir: Annotated[
        Optional[Path],
        typer.Option("--output-dir", help="Directory to save audio files (default: ./data or TRACKID_DATA_DIR)"),
    ] = None,
) -> None:
    """Identify a track from an audio file or URL.

    Examples:

        trackid identify song.mp3

        trackid identify "https://soundcloud.com/artist/mix" --time 7:45

        trackid identify "https://soundcloud.com/artist/mix" -t 7:45 -c 3
    """
    # Validate chunks
    chunks = max(1, min(5, chunks))

    # Parse time option
    timestamp = parse_time(time) if time else None

    # Require --time for URLs (downloading full mixes doesn't make sense)
    if is_url(source) and timestamp is None:
        err_console.print("[red]Error: --time is required for URLs[/red]")
        err_console.print("[dim]Hint: trackid identify \"https://...\" --time 7:45[/dim]")
        raise typer.Exit(1)

    # Determine services to use
    services = [service.value] if service != ServiceChoice.ALL else ["shazam", "acrcloud"]

    # Log if ACRCloud will be skipped
    if "acrcloud" in services and not settings.acrcloud_configured:
        err_console.print("[dim]ACRCloud: skipped (credentials not configured)[/dim]")
        services = [s for s in services if s != "acrcloud"]

    if not services:
        err_console.print("[red]No identification services available[/red]")
        raise typer.Exit(1)

    # Set up working directory
    if output_dir:
        work_dir = Path(output_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = None
    elif keep_files:
        work_dir = settings.resolved_data_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = None
    else:
        temp_dir = tempfile.mkdtemp(prefix="trackid_")
        work_dir = Path(temp_dir)

    try:
        # Handle URL vs local file
        if is_url(source):
            # Download specific time range based on chunks
            start_sec, end_sec = get_total_duration_for_chunks(timestamp, chunks)
            err_console.print(f"[dim]Downloading {format_time(start_sec)} - {format_time(end_sec)} from {source}...[/dim]")

            base = get_base_name(source)
            audio_path = work_dir / f"{base}_{timestamp}s.mp3"

            try:
                audio_path = download_audio(source, audio_path, start_sec, end_sec)
                err_console.print(f"[dim]Downloaded: {audio_path.stat().st_size // 1024}KB[/dim]")
            except DownloadError as e:
                err_console.print(f"[red]Download failed: {e}[/red]")
                raise typer.Exit(1)

            # Create chunks and identify
            match = identify_with_chunks(
                audio_path, timestamp, chunks, services, work_dir
            )
        else:
            # Local file
            audio_path = Path(source)
            if not audio_path.exists():
                err_console.print(f"[red]File not found: {source}[/red]")
                raise typer.Exit(1)

            if timestamp is not None and chunks > 1:
                # Extract and chunk from local file
                match = identify_with_chunks(
                    audio_path, timestamp, chunks, services, work_dir
                )
            else:
                match = identify_single(audio_path, services)

        # Output result
        print_match(match, output)

    finally:
        # Clean up temp directory
        if temp_dir and not keep_files:
            shutil.rmtree(temp_dir, ignore_errors=True)


def identify_single(audio_path: Path, services: list[str]) -> TrackMatch | None:
    """Identify a single audio file."""
    err_console.print(f"[dim]Identifying with {', '.join(services)}...[/dim]")

    matches = run_identify(audio_path, services)
    return matches[0] if matches else None


def identify_with_chunks(
    audio_path: Path,
    timestamp: int,
    num_chunks: int,
    services: list[str],
    work_dir: Path,
) -> TrackMatch | None:
    """Identify using multiple chunks, return first match."""
    boundaries = calculate_chunk_boundaries(timestamp, num_chunks)

    # For downloaded clips, the timestamp in the file is relative to start_sec
    # So we need to adjust chunk boundaries
    start_sec, _ = get_total_duration_for_chunks(timestamp, num_chunks)

    err_console.print(f"[dim]Trying {len(boundaries)} chunk(s) with {', '.join(services)}...[/dim]")

    chunks_dir = work_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    for i, (chunk_start, chunk_end) in enumerate(boundaries):
        # Adjust for the downloaded clip's start time
        relative_start = chunk_start - start_sec
        duration = chunk_end - chunk_start

        chunk_path = chunks_dir / f"chunk_{i:02d}.mp3"

        try:
            extract_segment(audio_path, chunk_path, relative_start, duration)
        except AudioError as e:
            err_console.print(f"[dim]Chunk {i}: extraction failed[/dim]")
            continue

        if not chunk_path.exists() or chunk_path.stat().st_size == 0:
            continue

        matches = run_identify(chunk_path, services)

        if matches:
            err_console.print(f"[dim]Chunk {i}: match found[/dim]")
            return matches[0]  # Return first match
        else:
            err_console.print(f"[dim]Chunk {i}: no match[/dim]")

    return None


@app.command()
def download(
    url: Annotated[
        str,
        typer.Argument(help="URL to download from"),
    ],
    output_file: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output file path"),
    ] = Path("audio.mp3"),
    start: Annotated[
        Optional[str],
        typer.Option("--start", "-s", help="Start time"),
    ] = None,
    end: Annotated[
        Optional[str],
        typer.Option("--end", "-e", help="End time"),
    ] = None,
) -> None:
    """Download audio from a URL.

    Examples:

        trackid download "https://soundcloud.com/artist/track" -o track.mp3

        trackid download "https://youtube.com/watch?v=..." -s 1:00 -e 2:00 -o clip.mp3
    """
    start_seconds = parse_time(start) if start else None
    end_seconds = parse_time(end) if end else None

    err_console.print(f"[dim]Downloading from {url}...[/dim]")

    try:
        result = download_audio(url, output_file, start_seconds, end_seconds)
        err_console.print(f"[dim]Size: {result.stat().st_size // 1024}KB[/dim]")
        out_console.print(f"{result}")
    except DownloadError as e:
        err_console.print(f"[red]Download failed: {e}[/red]")
        raise typer.Exit(1)


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = False,
) -> None:
    """trackid - Identify music tracks using Shazam and ACRCloud."""
    pass


if __name__ == "__main__":
    app()
