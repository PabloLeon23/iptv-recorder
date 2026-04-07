"""Tests for config load/save functions."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from iptv_recorder.config import (
    default_config,
    load_channel_cache,
    load_recordings,
    save_channel_cache,
    save_recordings,
)


class TestDefaultConfig:
    def test_has_required_sections(self):
        cfg = default_config()
        assert "iptv" in cfg
        assert "plex" in cfg

    def test_deep_copy_isolation(self):
        cfg1 = default_config()
        cfg1["iptv"]["format"] = "xtream"
        cfg2 = default_config()
        assert cfg2["iptv"]["format"] == ""


class TestLoadRecordings:
    def test_missing_file_returns_empty(self, tmp_path):
        with patch("iptv_recorder.config.RECORDINGS_FILE", tmp_path / "nope.json"):
            assert load_recordings() == []

    def test_corrupt_json_returns_empty(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{broken", encoding="utf-8")
        with patch("iptv_recorder.config.RECORDINGS_FILE", bad):
            assert load_recordings() == []

    def test_valid_json(self, tmp_path):
        f = tmp_path / "recs.json"
        f.write_text('[{"id": "1"}]', encoding="utf-8")
        with patch("iptv_recorder.config.RECORDINGS_FILE", f):
            result = load_recordings()
            assert len(result) == 1
            assert result[0]["id"] == "1"


class TestSaveRecordings:
    def test_round_trip(self, tmp_path):
        f = tmp_path / "recs.json"
        with (
            patch("iptv_recorder.config.RECORDINGS_FILE", f),
            patch("iptv_recorder.config.CONFIG_DIR", tmp_path),
            patch("iptv_recorder.config.TMP_DIR", tmp_path / "tmp"),
        ):
            data = [{"id": "abc", "status": "done"}]
            save_recordings(data)
            assert json.loads(f.read_text(encoding="utf-8")) == data


class TestChannelCache:
    def test_missing_returns_none(self, tmp_path):
        with patch("iptv_recorder.config.CACHE_FILE", tmp_path / "nope.json"):
            assert load_channel_cache() is None

    def test_corrupt_returns_none(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        with patch("iptv_recorder.config.CACHE_FILE", bad):
            assert load_channel_cache() is None

    def test_round_trip(self, tmp_path):
        f = tmp_path / "cache.json"
        with (
            patch("iptv_recorder.config.CACHE_FILE", f),
            patch("iptv_recorder.config.CONFIG_DIR", tmp_path),
            patch("iptv_recorder.config.TMP_DIR", tmp_path / "tmp"),
        ):
            channels = [{"id": "1", "name": "Test"}]
            save_channel_cache(channels)
            result = load_channel_cache()
            assert result == channels
