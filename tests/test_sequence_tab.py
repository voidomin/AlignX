import shutil

from streamlit.testing.v1 import AppTest

from src.frontend.tabs.sequence import (
    _build_projection_mapping,
    _parse_range_str,
)
from src.backend.sequence_viewer import (
    _aligned_cols_to_raw_residues,
    _build_chain_mapping_from_matches,
    find_motif_matches,
)


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

    def test_regex_metacharacters_in_the_query_are_treated_as_literal_text(self):
        # A query is a residue motif, not a real regex - characters like
        # parentheses/plus/dollar must match themselves (and thus find
        # nothing in a plain amino-acid sequence), not be interpreted as
        # regex syntax.
        assert find_motif_matches({"s1": "ACGT"}, "(A+)+$") == {}
        assert find_motif_matches({"s1": "AC(GT"}, "C(G") == {"s1": [2, 3, 4]}

    def test_catastrophic_backtracking_pattern_does_not_hang(self):
        # Regression for a ReDoS/regex-injection finding: this query would
        # cause exponential backtracking if compiled as a real regex against
        # a long non-matching sequence. Escaping it must keep this instant.
        query = "(A+)+B"
        sequence = "A" * 40 + "C"
        assert find_motif_matches({"s1": sequence}, query) == {}


class TestAlignedColsToRawResidues:
    def test_maps_columns_skipping_gaps(self):
        # "AC-GHK": col1=A(raw1) col2=C(raw2) col3=gap col4=G(raw3) col5=H(raw4) col6=K(raw5)
        assert _aligned_cols_to_raw_residues("AC-GHK", [4, 5, 6]) == [3, 4, 5]

    def test_gap_column_never_matches(self):
        assert _aligned_cols_to_raw_residues("AC-GHK", [3]) == []

    def test_empty_cols_returns_empty(self):
        assert _aligned_cols_to_raw_residues("ACGT", []) == []


class TestBuildChainMappingFromMatches:
    def test_maps_sequence_name_to_chain_letter(self):
        sequences = {"4RLT": "AC-GHK", "3UG9": "ACYGH-"}
        matches = {"4RLT": [4, 5, 6]}
        mapping = _build_chain_mapping_from_matches(sequences, matches)
        assert mapping == {"A": [3, 4, 5], "B": []}


class TestBuildProjectionMapping:
    def test_all_proteins_label_applies_to_every_sequence(self):
        sequences = {"s1": "AC-G", "s2": "ACGG"}
        selections = {"All Proteins (Alignment Columns)": "1, 2"}
        mapping = _build_projection_mapping(sequences, selections, n_total=4)
        assert mapping["A"] == [1, 2]
        assert mapping["B"] == [1, 2]

    def test_specific_protein_uses_raw_indices_directly(self):
        sequences = {"s1": "AC-G", "s2": "ACGG"}
        selections = {"s1": "1, 2"}
        mapping = _build_projection_mapping(sequences, selections, n_total=4)
        assert mapping["A"] == [1, 2]
        assert mapping["B"] == []

    def test_blank_selection_is_ignored(self):
        sequences = {"s1": "ACGT"}
        selections = {"s1": "   "}
        mapping = _build_projection_mapping(sequences, selections, n_total=4)
        assert mapping["A"] == []


def _run(script, tmp_path, monkeypatch):
    shutil.copy("config.yaml", tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_string(script)
    at.run(timeout=60)
    return at


INIT = """
import streamlit as st
from src.utils.session_manager import SessionInitializer
SessionInitializer.initialize()
"""


class TestRenderSequencesTab:
    def test_shows_unavailable_warning_without_sequences(self, tmp_path, monkeypatch):
        script = (
            INIT
            + 'results = {"stats": {"seq_identity": 0.0}}\n'
            + "from src.frontend.tabs.sequence import render_sequences_tab\n"
            + "render_sequences_tab(results)\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("unavailable" in w.value for w in at.warning)

    def test_renders_full_tab_with_real_sequences(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "results = {\n"
            + '    "stats": {"seq_identity": 87.5},\n'
            + '    "sequences": {"4RLT": "ACGHK", "3UG9": "ACYGK"},\n'
            + '    "conservation": [1.0, 1.0, 0.0, 0.0, 1.0],\n'
            + "}\n"
            + "from src.frontend.tabs.sequence import render_sequences_tab\n"
            + "render_sequences_tab(results)\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("87.5%" in m.value for m in at.metric)
        assert any("strictly conserved" in s.value for s in at.success)

    def test_motif_search_finds_and_reports_match(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "results = {\n"
            + '    "stats": {"seq_identity": 100.0},\n'
            + '    "sequences": {"4RLT": "ACGHK"},\n'
            + '    "conservation": [1.0, 1.0, 1.0, 1.0, 1.0],\n'
            + "}\n"
            + "from src.frontend.tabs.sequence import render_sequences_tab\n"
            + "render_sequences_tab(results)\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        at.text_input(key="motif_search_input").set_value("GHK").run()
        assert not at.exception
        assert any(
            "Found" in s.value and "matching residue" in s.value for s in at.success
        )
