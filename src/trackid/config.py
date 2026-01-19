"""Configuration management using environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings are prefixed with TRACKID_ in environment variables.
    Example: TRACKID_ACRCLOUD_ACCESS_KEY
    """

    # ACRCloud credentials
    acrcloud_host: str = "identify-eu-west-1.acrcloud.com"
    acrcloud_access_key: str = ""
    acrcloud_access_secret: str = ""
    acrcloud_timeout: int = 10

    # Paths
    data_dir: Path | None = None  # Default: $CWD/data
    temp_dir: Path = Path("/tmp/trackid")

    @property
    def resolved_data_dir(self) -> Path:
        """Get the data directory, defaulting to $CWD/data if not set."""
        if self.data_dir:
            return self.data_dir
        return Path.cwd() / "data"

    # External tools
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    ytdlp_path: str = "yt-dlp"

    # Defaults
    default_chunk_duration: int = 20

    model_config = {
        "env_prefix": "TRACKID_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def acrcloud_configured(self) -> bool:
        """Check if ACRCloud credentials are configured."""
        return bool(self.acrcloud_access_key and self.acrcloud_access_secret)

    @property
    def acrcloud_config(self) -> dict:
        """Get ACRCloud configuration dictionary."""
        return {
            "host": self.acrcloud_host,
            "access_key": self.acrcloud_access_key,
            "access_secret": self.acrcloud_access_secret,
            "timeout": self.acrcloud_timeout,
        }


# Global settings instance
settings = Settings()
