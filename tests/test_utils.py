"""Tests for trackid.utils module."""

import pytest
from trackid.utils import (
    parse_time,
    format_time,
    format_time_padded,
    get_base_name,
    is_url,
    sanitize_filename,
)


class TestParseTime:
    """Tests for parse_time function."""

    def test_seconds_only(self):
        assert parse_time("90") == 90

    def test_seconds_zero(self):
        assert parse_time("0") == 0

    def test_minutes_seconds(self):
        assert parse_time("1:30") == 90

    def test_minutes_seconds_zero_minutes(self):
        assert parse_time("0:45") == 45

    def test_hours_minutes_seconds(self):
        assert parse_time("1:23:45") == 5025

    def test_hours_minutes_seconds_zero_hours(self):
        assert parse_time("0:01:30") == 90

    def test_large_hours(self):
        assert parse_time("10:00:00") == 36000

    def test_whitespace_stripped(self):
        assert parse_time("  1:30  ") == 90

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            parse_time("invalid")

    def test_invalid_colon_format_raises(self):
        with pytest.raises(ValueError):
            parse_time("a:b:c")

    def test_too_many_colons_raises(self):
        with pytest.raises(ValueError):
            parse_time("1:2:3:4")


class TestFormatTime:
    """Tests for format_time function."""

    def test_under_minute(self):
        assert format_time(45) == "0:45"

    def test_exactly_one_minute(self):
        assert format_time(60) == "1:00"

    def test_minutes_and_seconds(self):
        assert format_time(90) == "1:30"

    def test_under_hour(self):
        assert format_time(3599) == "59:59"

    def test_exactly_one_hour(self):
        assert format_time(3600) == "1:00:00"

    def test_over_hour(self):
        assert format_time(3661) == "1:01:01"

    def test_always_include_hours(self):
        assert format_time(90, always_include_hours=True) == "0:01:30"

    def test_zero(self):
        assert format_time(0) == "0:00"

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            format_time(-1)


class TestFormatTimePadded:
    """Tests for format_time_padded function."""

    def test_under_hour(self):
        assert format_time_padded(90) == "00:01:30"

    def test_over_hour(self):
        assert format_time_padded(3661) == "01:01:01"

    def test_zero(self):
        assert format_time_padded(0) == "00:00:00"


class TestGetBaseName:
    """Tests for get_base_name function."""

    def test_soundcloud_url(self):
        url = "https://soundcloud.com/artist/track-name"
        assert get_base_name(url) == "artist_track-name"

    def test_soundcloud_url_trailing_slash(self):
        url = "https://soundcloud.com/artist/track-name/"
        assert get_base_name(url) == "artist_track-name"

    def test_youtube_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = get_base_name(url)
        assert "youtube" in result.lower() or "watch" in result.lower()

    def test_single_path_component(self):
        url = "https://example.com/track"
        assert "track" in get_base_name(url)

    def test_special_characters_sanitized(self):
        url = "https://soundcloud.com/artist/track?with=params"
        result = get_base_name(url)
        assert "?" not in result

    def test_long_url_truncated(self):
        url = "https://soundcloud.com/" + "a" * 200
        result = get_base_name(url)
        assert len(result) <= 100


class TestIsUrl:
    """Tests for is_url function."""

    def test_https_url(self):
        assert is_url("https://example.com") is True

    def test_http_url(self):
        assert is_url("http://example.com") is True

    def test_soundcloud_url(self):
        assert is_url("https://soundcloud.com/artist/track") is True

    def test_youtube_url(self):
        assert is_url("https://www.youtube.com/watch?v=abc") is True

    def test_local_path_unix(self):
        assert is_url("/path/to/file.mp3") is False

    def test_relative_path(self):
        assert is_url("./file.mp3") is False

    def test_just_filename(self):
        assert is_url("song.mp3") is False

    def test_domain_without_scheme(self):
        assert is_url("example.com/path") is True

    def test_whitespace_stripped(self):
        assert is_url("  https://example.com  ") is True


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_simple_name(self):
        assert sanitize_filename("song") == "song"

    def test_with_extension(self):
        assert sanitize_filename("song.mp3") == "song.mp3"

    def test_special_characters_replaced(self):
        # 9 special chars: < > : " / \ | ? *
        result = sanitize_filename('song<>:"/\\|?*.mp3')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_unicode_preserved(self):
        assert sanitize_filename("Café.mp3") == "Café.mp3"

    def test_long_name_truncated(self):
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 200
