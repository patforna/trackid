"""Shared utility functions."""

import re
from urllib.parse import urlparse


def parse_time(time_str: str) -> int:
    """Parse a time string to seconds.

    Supports formats:
        - "90" -> 90 seconds
        - "1:30" -> 90 seconds
        - "1:23:45" -> 5025 seconds

    Args:
        time_str: Time string in seconds, MM:SS, or HH:MM:SS format.

    Returns:
        Time in seconds.

    Raises:
        ValueError: If the time string is invalid.
    """
    time_str = time_str.strip()

    # Try pure integer (seconds)
    if time_str.isdigit():
        return int(time_str)

    parts = time_str.split(":")

    if len(parts) == 2:
        # MM:SS
        try:
            minutes, seconds = int(parts[0]), int(parts[1])
            return minutes * 60 + seconds
        except ValueError:
            raise ValueError(f"Invalid time format: {time_str}")

    elif len(parts) == 3:
        # HH:MM:SS
        try:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            raise ValueError(f"Invalid time format: {time_str}")

    raise ValueError(f"Invalid time format: {time_str}")


def format_time(seconds: int, always_include_hours: bool = False) -> str:
    """Format seconds as a time string.

    Args:
        seconds: Time in seconds.
        always_include_hours: If True, always include hours (HH:MM:SS).
                              If False, omit hours when zero (MM:SS).

    Returns:
        Formatted time string.
    """
    if seconds < 0:
        raise ValueError("Seconds cannot be negative")

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0 or always_include_hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_time_padded(seconds: int) -> str:
    """Format seconds as HH:MM:SS (always padded, for yt-dlp)."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def get_base_name(url: str) -> str:
    """Extract a base filename from a URL.

    For SoundCloud URLs like https://soundcloud.com/artist/track-name,
    returns "artist_track-name".

    Args:
        url: The URL to extract from.

    Returns:
        A filesystem-safe base name.
    """
    # Parse the URL
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    # Get the last two path components
    parts = path.split("/")
    parts = [p for p in parts if p]  # Remove empty strings

    if len(parts) >= 2:
        base = f"{parts[-2]}_{parts[-1]}"
    elif len(parts) == 1:
        base = parts[-1]
    else:
        # Fallback: sanitize the whole URL
        base = re.sub(r"[^\w\-]", "_", url)

    # Ensure it's filesystem-safe
    base = re.sub(r"[^\w\-]", "_", base)
    return base[:100]  # Limit length


def is_url(source: str) -> bool:
    """Check if a source string is a URL.

    Args:
        source: The source string to check.

    Returns:
        True if it looks like a URL, False otherwise.
    """
    source = source.strip()

    # Check for common URL schemes
    if source.startswith(("http://", "https://", "ftp://")):
        return True

    # Check for domain-like patterns without scheme
    if re.match(r"^[\w\-]+\.(com|org|net|io|co|me)", source):
        return True

    return False


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename.

    Args:
        name: The string to sanitize.

    Returns:
        A filesystem-safe string.
    """
    # Replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Remove control characters
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    # Limit length
    return name[:200]
