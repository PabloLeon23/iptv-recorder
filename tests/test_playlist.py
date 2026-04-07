"""Tests for playlist parsing and channel lookup."""

from iptv_recorder.playlist import _parse_extinf, find_channel


class TestParseExtinf:
    def test_standard_line(self):
        line = '#EXTINF:-1 tvg-id="ch1" tvg-name="Channel One" group-title="News",Channel One'
        tvg_id, group, name = _parse_extinf(line)
        assert tvg_id == "ch1"
        assert group == "News"
        assert name == "Channel One"

    def test_missing_attributes(self):
        line = "#EXTINF:-1,Just A Name"
        tvg_id, group, name = _parse_extinf(line)
        assert tvg_id == ""
        assert group == ""
        assert name == "Just A Name"

    def test_tvg_name_preferred_over_trailing(self):
        line = '#EXTINF:-1 tvg-name="Preferred",Trailing Name'
        _, _, name = _parse_extinf(line)
        assert name == "Preferred"

    def test_falls_back_to_trailing_name(self):
        line = '#EXTINF:-1 group-title="Sports",ESPN HD'
        _, group, name = _parse_extinf(line)
        assert group == "Sports"
        assert name == "ESPN HD"

    def test_malformed_line(self):
        tvg_id, group, name = _parse_extinf("not an extinf line")
        assert tvg_id == ""
        assert group == ""
        assert name == "not an extinf line"

    def test_empty_string(self):
        tvg_id, group, name = _parse_extinf("")
        assert tvg_id == ""
        assert group == ""
        assert name == ""

    def test_single_quotes(self):
        line = "#EXTINF:-1 tvg-id='abc' group-title='Drama',My Show"
        tvg_id, group, name = _parse_extinf(line)
        assert tvg_id == "abc"
        assert group == "Drama"


class TestFindChannel:
    CHANNELS = [
        {"id": "1", "name": "BBC One", "group": "UK", "url": "http://a"},
        {"id": "2", "name": "CNN International", "group": "News", "url": "http://b"},
        {"id": "3", "name": "ESPN", "group": "Sports", "url": "http://c"},
    ]

    def test_exact_match_case_insensitive(self):
        ch = find_channel(self.CHANNELS, "bbc one")
        assert ch is not None
        assert ch["id"] == "1"

    def test_match_by_id(self):
        ch = find_channel(self.CHANNELS, "2")
        assert ch is not None
        assert ch["name"] == "CNN International"

    def test_partial_match_fallback(self):
        ch = find_channel(self.CHANNELS, "International")
        assert ch is not None
        assert ch["id"] == "2"

    def test_no_match(self):
        assert find_channel(self.CHANNELS, "nonexistent") is None

    def test_empty_list(self):
        assert find_channel([], "anything") is None
