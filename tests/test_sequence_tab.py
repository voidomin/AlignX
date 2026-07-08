from src.frontend.tabs.sequence import _parse_range_str, find_motif_matches


class TestParseRangeStr:
    def test_parses_mixed_ranges_and_singles(self):
        assert _parse_range_str("1-3, 5, 7-8", 100) == [1, 2, 3, 5, 7, 8]

    def test_empty_string_returns_empty_list(self):
        assert _parse_range_str("", 100) == []
        assert _parse_range_str("   ", 100) == []

    def test_dedupes_and_sorts_overlapping_ranges(self):
        assert _parse_range_str("5, 1-3, 2", 100) == [1, 2, 3, 5]

    def test_clamps_to_max_val(self):
        assert _parse_range_str("1-10", 5) == [1, 2, 3, 4, 5]
        assert _parse_range_str("10", 5) == []

    def test_ignores_malformed_and_reversed_tokens(self):
        assert _parse_range_str("abc, 5-3, 1", 10) == [1]


class TestFindMotifMatches:
    def test_finds_exact_motif_at_correct_aligned_column(self):
        # s1 raw (gap-stripped) = "ACGHK"; "G.K" matches "GHK" at raw idx 2-4
        # -> aligned columns 4,5,6 (aligned seq has a gap at column 3).
        matches = find_motif_matches({"s1": "AC-GHK"}, "G.K")
        assert matches == {"s1": [4, 5, 6]}

    def test_sequence_with_no_match_is_omitted(self):
        matches = find_motif_matches({"s1": "AC-GHK", "s2": "ACYGH-"}, "G.K")
        assert "s2" not in matches

    def test_empty_query_returns_empty_dict(self):
        assert find_motif_matches({"s1": "ACGT"}, "") == {}

    def test_invalid_regex_returns_empty_dict_instead_of_raising(self):
        assert find_motif_matches({"s1": "ACGT"}, "(") == {}

    def test_wildcard_characters_x_and_dash_both_work(self):
        assert find_motif_matches({"s1": "ACGT"}, "AXG") == {"s1": [1, 2, 3]}
        assert find_motif_matches({"s1": "ACGT"}, "A-G") == {"s1": [1, 2, 3]}
