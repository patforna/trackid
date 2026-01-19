"""Track identification using Shazam and ACRCloud."""

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from shazamio import Shazam

from .config import settings


class Service(str, Enum):
    """Available identification services."""

    SHAZAM = "shazam"
    ACRCLOUD = "acrcloud"
    ALL = "all"


@dataclass
class TrackMatch:
    """A matched track from identification."""

    title: str
    artist: str
    service: str
    album: str | None = None
    url: str | None = None
    confidence: float | None = None
    timestamp: int | None = None  # Position in source file (seconds)
    raw_response: dict = field(default_factory=dict, repr=False)


class IdentificationError(Exception):
    """Error during track identification."""

    pass


async def identify_shazam(audio_path: Path) -> TrackMatch | None:
    """Identify a track using Shazam.

    Args:
        audio_path: Path to the audio file.

    Returns:
        TrackMatch if identified, None otherwise.
    """
    try:
        shazam = Shazam()
        result = await shazam.recognize(str(audio_path))

        if result and "track" in result:
            track = result["track"]

            # Try to extract album from sections metadata
            album = None
            sections = track.get("sections", [])
            if sections:
                metadata = sections[0].get("metadata", [])
                if metadata:
                    album = metadata[0].get("text")

            return TrackMatch(
                title=track.get("title", "Unknown"),
                artist=track.get("subtitle", "Unknown"),
                album=album,
                url=track.get("url"),
                service="shazam",
                raw_response=result,
            )

    except Exception:
        # Shazam can fail for various reasons, don't raise
        pass

    return None


def identify_acrcloud(audio_path: Path) -> TrackMatch | None:
    """Identify a track using ACRCloud.

    Args:
        audio_path: Path to the audio file.

    Returns:
        TrackMatch if identified, None otherwise.
        Returns None if ACRCloud is not configured.
    """
    if not settings.acrcloud_configured:
        return None

    try:
        from acrcloud.recognizer import ACRCloudRecognizer

        recognizer = ACRCloudRecognizer(settings.acrcloud_config)
        result_str = recognizer.recognize_by_file(str(audio_path), 0)
        result = json.loads(result_str)

        if result.get("status", {}).get("code") == 0:
            music = result.get("metadata", {}).get("music", [])
            if music:
                track = music[0]

                # Extract artist
                artists = track.get("artists", [])
                artist = artists[0].get("name", "Unknown") if artists else "Unknown"

                # Extract album
                album_info = track.get("album", {})
                album = album_info.get("name") if album_info else None

                # Try to get external URLs (Spotify, etc.)
                external = track.get("external_metadata", {})
                spotify = external.get("spotify", {})
                spotify_track = spotify.get("track", {})
                spotify_id = spotify_track.get("id")
                url = f"https://open.spotify.com/track/{spotify_id}" if spotify_id else None

                return TrackMatch(
                    title=track.get("title", "Unknown"),
                    artist=artist,
                    album=album,
                    url=url,
                    confidence=track.get("score"),
                    service="acrcloud",
                    raw_response=result,
                )

    except ImportError:
        raise IdentificationError("pyacrcloud not installed")
    except Exception:
        # ACRCloud can fail for various reasons
        pass

    return None


async def identify_track(
    audio_path: Path,
    services: list[str] | None = None,
) -> list[TrackMatch]:
    """Identify a track using specified services.

    Args:
        audio_path: Path to the audio file.
        services: List of services to use ("shazam", "acrcloud").
                  If None or ["all"], uses all available services.

    Returns:
        List of TrackMatch objects (may be empty if no matches).
    """
    if services is None or "all" in services:
        services = ["shazam", "acrcloud"]

    matches = []

    for service in services:
        if service == "shazam":
            match = await identify_shazam(audio_path)
            if match:
                matches.append(match)

        elif service == "acrcloud":
            if settings.acrcloud_configured:
                match = identify_acrcloud(audio_path)
                if match:
                    matches.append(match)

    return matches


async def identify_multiple(
    audio_paths: list[Path],
    services: list[str] | None = None,
    delay: float = 0.2,
) -> list[TrackMatch]:
    """Identify multiple audio files.

    Useful for identifying chunks of a longer audio file.

    Args:
        audio_paths: List of paths to audio files.
        services: List of services to use.
        delay: Delay between requests to avoid rate limiting.

    Returns:
        List of unique TrackMatch objects found across all files.
    """
    seen = set()  # Track (artist, title) pairs we've seen
    matches = []

    for audio_path in audio_paths:
        results = await identify_track(audio_path, services)

        for match in results:
            key = (match.artist.lower(), match.title.lower())
            if key not in seen:
                seen.add(key)
                matches.append(match)

        if delay > 0:
            await asyncio.sleep(delay)

    return matches


def run_identify(
    audio_path: Path,
    services: list[str] | None = None,
) -> list[TrackMatch]:
    """Synchronous wrapper for identify_track.

    Args:
        audio_path: Path to the audio file.
        services: List of services to use.

    Returns:
        List of TrackMatch objects.
    """
    return asyncio.run(identify_track(audio_path, services))


def run_identify_multiple(
    audio_paths: list[Path],
    services: list[str] | None = None,
    delay: float = 0.2,
) -> list[TrackMatch]:
    """Synchronous wrapper for identify_multiple.

    Args:
        audio_paths: List of paths to audio files.
        services: List of services to use.
        delay: Delay between requests.

    Returns:
        List of unique TrackMatch objects.
    """
    return asyncio.run(identify_multiple(audio_paths, services, delay))
