import pytest

from src.backend.sequence_viewer import SequenceViewer


class TestParseAfasta:
    def test_parses_multiple_sequences(self, tmp_path):
        afasta = tmp_path / "align.afasta"
        afasta.write_text(">seq1\nAC-GT\n>seq2\nACGGT\n")
        viewer = SequenceViewer()

        result = viewer.parse_afasta(afasta)

        assert result == {"seq1": "AC-GT", "seq2": "ACGGT"}

    def test_joins_wrapped_sequence_lines(self, tmp_path):
        afasta = tmp_path / "align.afasta"
        afasta.write_text(">seq1\nACGT\nACGT\n")
        viewer = SequenceViewer()

        result = viewer.parse_afasta(afasta)

        assert result == {"seq1": "ACGTACGT"}

    def test_skips_blank_lines(self, tmp_path):
        afasta = tmp_path / "align.afasta"
        afasta.write_text(">seq1\n\nACGT\n\n")
        viewer = SequenceViewer()

        result = viewer.parse_afasta(afasta)

        assert result == {"seq1": "ACGT"}

    def test_returns_none_on_missing_file(self, tmp_path):
        viewer = SequenceViewer()
        assert viewer.parse_afasta(tmp_path / "nope.afasta") is None

    def test_returns_none_on_read_failure(self, tmp_path):
        viewer = SequenceViewer()
        assert viewer.parse_afasta(tmp_path) is None


class TestCalculateConservation:
    def test_empty_sequences_returns_empty_list(self):
        viewer = SequenceViewer()
        assert viewer.calculate_conservation({}) == []

    def test_identical_column_scores_one(self):
        viewer = SequenceViewer()
        scores = viewer.calculate_conservation({"a": "AA", "b": "AA"})
        assert scores == [1.0, 1.0]

    def test_split_column_scores_fraction(self):
        viewer = SequenceViewer()
        scores = viewer.calculate_conservation({"a": "A", "b": "A", "c": "G"})
        assert scores == [pytest.approx(2 / 3)]


class TestResidueCellHtml:
    def test_gap_uses_gap_color(self):
        viewer = SequenceViewer()
        html = viewer._residue_cell_html("-", 1.0)
        assert viewer.colors["gap"] in html
        assert ">-</td>" in html

    def test_identical_column_uses_identity_color(self):
        viewer = SequenceViewer()
        html = viewer._residue_cell_html("A", 1.0)
        assert viewer.colors["identity"] in html

    def test_high_similarity_uses_high_sim_color(self):
        viewer = SequenceViewer()
        html = viewer._residue_cell_html("A", 0.8)
        assert viewer.colors["high_similarity"] in html

    def test_low_similarity_uses_default_color(self):
        viewer = SequenceViewer()
        html = viewer._residue_cell_html("A", 0.2)
        assert viewer.colors["default"] in html
        assert 'class=""' in html


class TestConsensusSymbol:
    def test_full_identity(self):
        assert SequenceViewer._consensus_symbol(1.0) == "*"

    def test_high_similarity(self):
        assert SequenceViewer._consensus_symbol(0.8) == ":"

    def test_moderate_similarity(self):
        assert SequenceViewer._consensus_symbol(0.6) == "."

    def test_low_similarity(self):
        assert SequenceViewer._consensus_symbol(0.1) == "&nbsp;"


class TestGenerateHtml:
    def test_includes_headers_and_consensus_row(self):
        viewer = SequenceViewer()
        sequences = {"seq1": "AC", "seq2": "AG"}
        conservation = [1.0, 0.5]

        html = viewer.generate_html(sequences, conservation)

        assert "seq1" in html
        assert "seq2" in html
        assert "Consensus" in html
        assert "<table" in html


class TestCalculateIdentity:
    def test_empty_sequences_returns_zero(self):
        viewer = SequenceViewer()
        assert viewer.calculate_identity({}) == 0.0

    def test_single_sequence_returns_hundred(self):
        viewer = SequenceViewer()
        assert viewer.calculate_identity({"a": "ACGT"}) == 100.0

    def test_two_identical_sequences_returns_hundred(self):
        viewer = SequenceViewer()
        assert viewer.calculate_identity({"a": "ACGT", "b": "ACGT"}) == 100.0

    def test_ignores_gap_gap_matches(self):
        viewer = SequenceViewer()
        # Position 2 is a gap-gap "match" that should not count toward identity.
        result = viewer.calculate_identity({"a": "AC-T", "b": "AG-T"})
        assert result == pytest.approx(2 / 4 * 100)

    def test_averages_across_all_pairs(self):
        viewer = SequenceViewer()
        result = viewer.calculate_identity({"a": "AAAA", "b": "AAAA", "c": "GGGG"})
        # a-b: 100%, a-c: 0%, b-c: 0% -> average 33.33%
        assert result == pytest.approx(100 / 3)

    def test_skips_zero_length_pairs(self):
        viewer = SequenceViewer()
        result = viewer.calculate_identity({"a": "", "b": "", "c": "ACGT", "d": "ACGT"})
        # a-b (both empty) is skipped entirely; only c-d (100%) contributes.
        assert result == 100.0
