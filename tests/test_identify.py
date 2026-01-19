"""Tests for trackid.identify module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from trackid.identify import (
    identify_shazam,
    identify_acrcloud,
    identify_track,
    TrackMatch,
)


class TestIdentifyShazam:
    """Tests for identify_shazam function."""

    @pytest.mark.asyncio
    @patch("trackid.identify.Shazam")
    async def test_successful_identification(
        self, mock_shazam_class, mock_shazam_response, temp_audio_dir
    ):
        mock_shazam = AsyncMock()
        mock_shazam.recognize.return_value = mock_shazam_response
        mock_shazam_class.return_value = mock_shazam

        audio_file = temp_audio_dir / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        result = await identify_shazam(audio_file)

        assert result is not None
        assert result.title == "Dreams"
        assert result.artist == "Fleetwood Mac"
        assert result.album == "Rumours"
        assert result.service == "shazam"
        assert result.url == "https://www.shazam.com/track/123456"

    @pytest.mark.asyncio
    @patch("trackid.identify.Shazam")
    async def test_no_match_returns_none(
        self, mock_shazam_class, mock_shazam_no_match, temp_audio_dir
    ):
        mock_shazam = AsyncMock()
        mock_shazam.recognize.return_value = mock_shazam_no_match
        mock_shazam_class.return_value = mock_shazam

        audio_file = temp_audio_dir / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        result = await identify_shazam(audio_file)

        assert result is None

    @pytest.mark.asyncio
    @patch("trackid.identify.Shazam")
    async def test_exception_returns_none(self, mock_shazam_class, temp_audio_dir):
        mock_shazam = AsyncMock()
        mock_shazam.recognize.side_effect = Exception("API error")
        mock_shazam_class.return_value = mock_shazam

        audio_file = temp_audio_dir / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        result = await identify_shazam(audio_file)

        assert result is None


class TestIdentifyAcrcloud:
    """Tests for identify_acrcloud function."""

    @patch("trackid.identify.settings")
    @patch("trackid.identify.ACRCloudRecognizer", create=True)
    def test_successful_identification(
        self, mock_recognizer_class, mock_settings, mock_acrcloud_response, temp_audio_dir
    ):
        import json

        mock_settings.acrcloud_configured = True
        mock_settings.acrcloud_config = {
            "host": "test.acrcloud.com",
            "access_key": "test_key",
            "access_secret": "test_secret",
            "timeout": 10,
        }

        mock_recognizer = MagicMock()
        mock_recognizer.recognize_by_file.return_value = json.dumps(mock_acrcloud_response)
        mock_recognizer_class.return_value = mock_recognizer

        # Patch the import inside the function
        with patch.dict("sys.modules", {"acrcloud.recognizer": MagicMock(ACRCloudRecognizer=mock_recognizer_class)}):
            audio_file = temp_audio_dir / "test.mp3"
            audio_file.write_bytes(b"fake audio")

            result = identify_acrcloud(audio_file)

            assert result is not None
            assert result.title == "Dreams"
            assert result.artist == "Fleetwood Mac"
            assert result.album == "Rumours"
            assert result.service == "acrcloud"
            assert result.confidence == 95
            assert "spotify.com" in result.url

    @patch("trackid.identify.settings")
    def test_returns_none_when_not_configured(self, mock_settings, temp_audio_dir):
        mock_settings.acrcloud_configured = False

        audio_file = temp_audio_dir / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        result = identify_acrcloud(audio_file)
        assert result is None

    @patch("trackid.identify.settings")
    @patch("trackid.identify.ACRCloudRecognizer", create=True)
    def test_no_match_returns_none(
        self, mock_recognizer_class, mock_settings, mock_acrcloud_no_match, temp_audio_dir
    ):
        import json

        mock_settings.acrcloud_configured = True
        mock_settings.acrcloud_config = {}

        mock_recognizer = MagicMock()
        mock_recognizer.recognize_by_file.return_value = json.dumps(mock_acrcloud_no_match)
        mock_recognizer_class.return_value = mock_recognizer

        with patch.dict("sys.modules", {"acrcloud.recognizer": MagicMock(ACRCloudRecognizer=mock_recognizer_class)}):
            audio_file = temp_audio_dir / "test.mp3"
            audio_file.write_bytes(b"fake audio")

            result = identify_acrcloud(audio_file)

            assert result is None


class TestIdentifyTrack:
    """Tests for identify_track function."""

    @pytest.mark.asyncio
    @patch("trackid.identify.identify_acrcloud")
    @patch("trackid.identify.identify_shazam")
    async def test_uses_all_services_by_default(
        self, mock_shazam, mock_acrcloud, temp_audio_dir
    ):
        mock_shazam.return_value = TrackMatch(
            title="Dreams",
            artist="Fleetwood Mac",
            service="shazam",
        )
        mock_acrcloud.return_value = None

        # Mock settings for acrcloud
        with patch("trackid.identify.settings") as mock_settings:
            mock_settings.acrcloud_configured = True

            audio_file = temp_audio_dir / "test.mp3"
            audio_file.write_bytes(b"fake audio")

            results = await identify_track(audio_file)

            mock_shazam.assert_called_once()
            mock_acrcloud.assert_called_once()
            assert len(results) == 1
            assert results[0].title == "Dreams"

    @pytest.mark.asyncio
    @patch("trackid.identify.identify_shazam")
    async def test_uses_only_specified_service(self, mock_shazam, temp_audio_dir):
        mock_shazam.return_value = TrackMatch(
            title="Dreams",
            artist="Fleetwood Mac",
            service="shazam",
        )

        audio_file = temp_audio_dir / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        results = await identify_track(audio_file, services=["shazam"])

        mock_shazam.assert_called_once()
        assert len(results) == 1

    @pytest.mark.asyncio
    @patch("trackid.identify.identify_shazam")
    async def test_returns_empty_list_on_no_match(self, mock_shazam, temp_audio_dir):
        mock_shazam.return_value = None

        audio_file = temp_audio_dir / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        results = await identify_track(audio_file, services=["shazam"])

        assert results == []


class TestTrackMatch:
    """Tests for TrackMatch dataclass."""

    def test_creation(self):
        match = TrackMatch(
            title="Dreams",
            artist="Fleetwood Mac",
            service="shazam",
        )

        assert match.title == "Dreams"
        assert match.artist == "Fleetwood Mac"
        assert match.service == "shazam"
        assert match.album is None
        assert match.url is None
        assert match.confidence is None
        assert match.timestamp is None

    def test_with_all_fields(self):
        match = TrackMatch(
            title="Dreams",
            artist="Fleetwood Mac",
            service="shazam",
            album="Rumours",
            url="https://example.com",
            confidence=95.5,
            timestamp=120,
        )

        assert match.album == "Rumours"
        assert match.url == "https://example.com"
        assert match.confidence == 95.5
        assert match.timestamp == 120
