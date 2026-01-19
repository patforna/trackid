"""Pytest fixtures for trackid tests."""

import pytest
from pathlib import Path


@pytest.fixture
def mock_shazam_response():
    """Mock successful Shazam response."""
    return {
        "track": {
            "title": "Dreams",
            "subtitle": "Fleetwood Mac",
            "url": "https://www.shazam.com/track/123456",
            "sections": [
                {
                    "metadata": [
                        {"text": "Rumours"}
                    ]
                }
            ],
        }
    }


@pytest.fixture
def mock_shazam_no_match():
    """Mock Shazam response with no match."""
    return {}


@pytest.fixture
def mock_acrcloud_response():
    """Mock successful ACRCloud response."""
    return {
        "status": {"code": 0, "msg": "Success"},
        "metadata": {
            "music": [
                {
                    "title": "Dreams",
                    "artists": [{"name": "Fleetwood Mac"}],
                    "album": {"name": "Rumours"},
                    "score": 95,
                    "external_metadata": {
                        "spotify": {
                            "track": {"id": "0ofHAoxe9vBkTCp2UQIavz"}
                        }
                    },
                }
            ]
        },
    }


@pytest.fixture
def mock_acrcloud_no_match():
    """Mock ACRCloud response with no match."""
    return {
        "status": {"code": 1001, "msg": "No result"},
        "metadata": {},
    }


@pytest.fixture
def temp_audio_dir(tmp_path):
    """Temporary directory for audio files."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    return audio_dir
