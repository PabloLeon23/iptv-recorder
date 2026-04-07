"""Tests for recorder helpers: sanitize, conflicts, cleanup, build_plex_filename."""

from datetime import datetime, timezone
from pathlib import Path

from iptv_recorder.recorder import (
    _build_cmd,
    build_plex_filename,
    cleanup_stale_recordings,
    find_conflicts,
    sanitize_filename,
)


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    def test_removes_illegal_chars(self):
        assert sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"

    def test_strips_dots_and_spaces(self):
        assert sanitize_filename("  ..hello.. ") == "hello"

    def test_empty_becomes_unknown(self):
        assert sanitize_filename("") == "Unknown_Channel"

    def test_only_illegal_chars(self):
        assert sanitize_filename('":*?') == "Unknown_Channel"

    def test_control_chars_removed(self):
        assert sanitize_filename("hello\x00world\x1f") == "helloworld"

    def test_unicode_preserved(self):
        assert sanitize_filename("Canal+ España") == "Canal+ España"

    def test_already_clean(self):
        assert sanitize_filename("My Channel") == "My Channel"


# ---------------------------------------------------------------------------
# cleanup_stale_recordings
# ---------------------------------------------------------------------------

class TestCleanupStaleRecordings:
    def test_marks_past_recording_as_failed(self):
        recs = [
            {"status": "recording", "end": "2020-01-01T00:00:00+00:00"},
        ]
        result = cleanup_stale_recordings(recs)
        assert result[0]["status"] == "failed"

    def test_keeps_future_recording(self):
        recs = [
            {"status": "recording", "end": "2099-01-01T00:00:00+00:00"},
        ]
        result = cleanup_stale_recordings(recs)
        assert result[0]["status"] == "recording"

    def test_ignores_done_status(self):
        recs = [
            {"status": "done", "end": "2020-01-01T00:00:00+00:00"},
        ]
        result = cleanup_stale_recordings(recs)
        assert result[0]["status"] == "done"

    def test_skips_missing_end(self):
        recs = [{"status": "recording"}]
        result = cleanup_stale_recordings(recs)
        assert result[0]["status"] == "recording"

    def test_handles_invalid_end_format(self):
        recs = [{"status": "recording", "end": "not-a-date"}]
        result = cleanup_stale_recordings(recs)
        assert result[0]["status"] == "recording"

    def test_empty_list(self):
        assert cleanup_stale_recordings([]) == []


# ---------------------------------------------------------------------------
# find_conflicts
# ---------------------------------------------------------------------------

class TestFindConflicts:
    def _make_rec(self, start, end, status="scheduled"):
        return {"start": start, "end": end, "status": status, "channel_name": "test"}

    def test_overlapping_intervals(self):
        rec = self._make_rec("2025-06-01T10:00:00+00:00", "2025-06-01T12:00:00+00:00")
        conflicts = find_conflicts(
            datetime(2025, 6, 1, 11, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 1, 13, 0, tzinfo=timezone.utc),
            [rec],
        )
        assert len(conflicts) == 1

    def test_non_overlapping(self):
        rec = self._make_rec("2025-06-01T10:00:00+00:00", "2025-06-01T11:00:00+00:00")
        conflicts = find_conflicts(
            datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 1, 13, 0, tzinfo=timezone.utc),
            [rec],
        )
        assert len(conflicts) == 0

    def test_adjacent_intervals_no_conflict(self):
        rec = self._make_rec("2025-06-01T10:00:00+00:00", "2025-06-01T11:00:00+00:00")
        conflicts = find_conflicts(
            datetime(2025, 6, 1, 11, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
            [rec],
        )
        assert len(conflicts) == 0

    def test_skips_done_status(self):
        rec = self._make_rec(
            "2025-06-01T10:00:00+00:00", "2025-06-01T12:00:00+00:00", status="done"
        )
        conflicts = find_conflicts(
            datetime(2025, 6, 1, 11, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 1, 13, 0, tzinfo=timezone.utc),
            [rec],
        )
        assert len(conflicts) == 0

    def test_open_ended_always_conflicts(self):
        rec = {"status": "recording", "start": "2025-06-01T10:00:00+00:00", "end": None}
        conflicts = find_conflicts(
            datetime(2025, 6, 1, 20, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 1, 21, 0, tzinfo=timezone.utc),
            [rec],
        )
        assert len(conflicts) == 1

    def test_malformed_dates_skipped(self):
        rec = {"status": "scheduled", "start": "bad", "end": "bad"}
        conflicts = find_conflicts(
            datetime(2025, 6, 1, 11, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
            [rec],
        )
        assert len(conflicts) == 0

    def test_empty_recordings(self):
        assert find_conflicts(
            datetime(2025, 6, 1, 11, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
            [],
        ) == []


# ---------------------------------------------------------------------------
# build_plex_filename
# ---------------------------------------------------------------------------

class TestBuildPlexFilename:
    def test_unique_name(self, tmp_path):
        start = datetime(2025, 6, 15, 20, 0, tzinfo=timezone.utc)
        name = build_plex_filename("My Channel", start, tmp_path)
        assert name == "My Channel (2025).mp4"

    def test_disambiguates_existing(self, tmp_path):
        start = datetime(2025, 6, 15, 20, 0, tzinfo=timezone.utc)
        (tmp_path / "My Channel (2025).mp4").touch()
        name = build_plex_filename("My Channel", start, tmp_path)
        assert name.startswith("My Channel (2025) [")
        assert name.endswith("].mp4")

    def test_sanitizes_channel_name(self, tmp_path):
        start = datetime(2025, 6, 15, 20, 0, tzinfo=timezone.utc)
        name = build_plex_filename("Bad:Name?", start, tmp_path)
        assert ":" not in name
        assert "?" not in name


# ---------------------------------------------------------------------------
# _build_cmd
# ---------------------------------------------------------------------------

class TestBuildCmd:
    def test_with_duration(self):
        cmd = _build_cmd("/usr/bin/ffmpeg", "http://stream", "/tmp/out.mp4", 60)
        assert "-t" in cmd
        assert "60" in cmd
        assert cmd[0] == "/usr/bin/ffmpeg"

    def test_without_duration(self):
        cmd = _build_cmd("/usr/bin/ffmpeg", "http://stream", "/tmp/out.mp4", None)
        assert "-t" not in cmd
