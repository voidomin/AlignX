"""
Sequence alignment visualization module.
Parses Mustang .afasta files and generates interactive HTML views.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from src.utils.logger import get_logger

logger = get_logger()


class SequenceViewer:
    def __init__(self):
        # Use CSS variables for theme-aware colors
        # These will be defined in the HTML/CSS
        self.colors = {
            "identity": "var(--seq-identity, #ff6b6b)",
            "high_similarity": "var(--seq-high-sim, #feca57)",
            "gap": "var(--seq-gap, #dfe6e9)",
            "default": "var(--seq-default, transparent)",
        }

    def parse_afasta(self, file_path: Path) -> Optional[Dict[str, str]]:
        """
        Parse Mustang AFASTA alignment file.

        Args:
            file_path: Path to .afasta file

        Returns:
            Dictionary of {header: sequence} or None if failed
        """
        try:
            sequences = {}
            current_header = None
            current_seq = []

            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith(">"):
                        if current_header:
                            sequences[current_header] = "".join(current_seq)
                        current_header = line[1:].strip()  # Remove >
                        current_seq = []
                    else:
                        current_seq.append(line)

                # Add last sequence
                if current_header:
                    sequences[current_header] = "".join(current_seq)

            return sequences

        except Exception:
            logger.exception("Failed to parse AFASTA file")
            return None

    def calculate_conservation(self, sequences: Dict[str, str]) -> List[float]:
        """
        Calculate conservation score (0.0-1.0) for each position.
        Simple identity based score.
        """
        if not sequences:
            return []

        seq_list = list(sequences.values())
        length = len(seq_list[0])
        scores = []

        for i in range(length):
            residues = [s[i] for s in seq_list]

            # Filter gaps for calculations if needed, but for visualization strict identity checks gaps too
            # Here we count unique residues ignoring gaps? No, gaps matter in alignment.

            # Simple approach: Fraction of most common residue
            _, counts = np.unique(residues, return_counts=True)
            max_count = np.max(counts)
            score = max_count / len(seq_list)

            # If gap is the most common, score should be low? Or handle separately.
            # Let's keep raw agreement score for now.
            scores.append(score)

        return scores

    def _residue_cell_html(self, char: str, score: float) -> str:
        """One <td> for a single aligned residue, colored by how conserved
        its column is (or flagged as a gap)."""
        if char == "-":
            bg_color = self.colors["gap"]
        elif score >= 1.0:  # Identical column
            bg_color = self.colors["identity"]
        elif score > 0.7:  # High similarity
            bg_color = self.colors["high_similarity"]
        else:
            bg_color = self.colors["default"]

        res_class = "res-val" if score > 0.5 or char == "-" else ""
        return f'<td class="{res_class}" style="background-color: {bg_color}; font-family: monospace; width: 20px; text-align: center;">{char}</td>'

    @staticmethod
    def _consensus_symbol(score: float) -> str:
        if score >= 1.0:
            return "*"
        if score > 0.7:
            return ":"
        if score > 0.5:
            return "."
        return "&nbsp;"

    def generate_html(
        self, sequences: Dict[str, str], conservation: List[float]
    ) -> str:
        """
        Generate HTML/CSS for scrollable alignment view.
        """

        # Build Grid Rows
        rows_html = ""

        # 1. Header (Conservation Bar? Maybe later)

        # 2. Sequence Rows
        for header, seq in sequences.items():
            residues_html = "".join(
                self._residue_cell_html(char, conservation[i])
                for i, char in enumerate(seq)
            )

            rows_html += f"""
            <tr>
                <td style="position: sticky; left: 0; background: var(--st-sticky-bg, #fff); color: var(--st-text-color, black); z-index: 2; padding-right: 15px; font-weight: bold; border-right: 2px solid var(--st-divider-color, #ddd); white-space: nowrap; min-width: 150px;">{header}</td>
                {residues_html}
            </tr>
            """

        # Consensus/Conservation Row
        cons_html = "".join(
            f'<td style="text-align: center; font-weight: bold;">{self._consensus_symbol(score)}</td>'
            for score in conservation
        )

        rows_html += f"""
        <tr style="background-color: var(--st-secondary-bg, #f1f2f6);">
            <td style="position: sticky; left: 0; background: var(--st-secondary-bg, #f1f2f6); border-right: 2px solid var(--st-divider-color, #ddd); color: var(--st-text-color, black); white-space: nowrap; font-weight: bold; z-index: 2;">Consensus</td>
            {cons_html}
        </tr>
        """

        html = f"""
        <style>
            :root {{
                --seq-identity: #ff4757;
                --seq-high-sim: #ffa502;
                --seq-gap: #ced6e0;
                --st-sticky-bg: #1e1e1e; /* Default dark context, will be overridden if in light */
                --st-text-color: #f1f2f6;
                --st-divider-color: rgba(255, 255, 255, 0.1);
                --st-secondary-bg: #2f3542;
            }}
            
            @media (prefers-color-scheme: light) {{
                :root {{
                    --st-sticky-bg: #ffffff;
                    --st-text-color: #2f3542;
                    --st-divider-color: #ddd;
                    --st-secondary-bg: #f1f2f6;
                    --seq-gap: #dfe6e9;
                }}
            }}

            /* High contrast for colored cells */
            .res-val {{ color: #ffffff !important; font-weight: bold; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }}
            
            /* Ensure the table doesn't collapse */
            .alignment-table th, .alignment-table td {{
                padding: 2px 4px;
                border: 0.1px solid rgba(128,128,128,0.1);
            }}
        </style>
        <div style="overflow-x: auto; font-family: 'Courier New', monospace; font-size: 14px; color: var(--st-text-color); background: var(--st-sticky-bg);">
            <table class="alignment-table" style="border-collapse: collapse; min-width: 100%; table-layout: fixed;">
                {rows_html}
            </table>
        </div>
        """
        return html

    def calculate_identity(self, sequences: Dict[str, str]) -> float:
        """
        Calculate average pairwise sequence identity (0-100%).
        Ignores gap-gap matches.
        """
        if not sequences:
            return 0.0

        seqs = list(sequences.values())
        n = len(seqs)
        if n < 2:
            return 100.0 if n == 1 else 0.0

        import itertools

        identities = []
        for s1, s2 in itertools.combinations(seqs, 2):
            matches = sum(
                1 for a, b in zip(s1, s2, strict=False) if a == b and a != "-"
            )
            length = len(s1)
            # Avoid division by zero
            if length == 0:
                continue
            # Identity = Matches / Total Alignment Length * 100
            identities.append((matches / length) * 100)

        return sum(identities) / len(identities) if identities else 0.0


# Sequence motif search - shared between the Streamlit tab
# (src/frontend/tabs/sequence.py, which imports these rather than defining
# them, to keep one implementation) and the SPA's GET /api/sequence motif
# query param. Pure functions, no Streamlit/FastAPI dependency.


def _raw_to_aligned_map(aligned_seq: str) -> Tuple[str, Dict[int, int]]:
    """Strips gaps from an aligned sequence, returning the raw (ungapped)
    sequence and a map from raw (0-indexed) position to aligned (1-indexed)
    column - lets a match found in the raw sequence be reported at its real
    alignment column."""
    raw_chars = []
    raw_to_aligned = {}
    current_raw_idx = 0
    for aligned_idx, char in enumerate(aligned_seq):
        if char != "-":
            raw_chars.append(char)
            raw_to_aligned[current_raw_idx] = aligned_idx + 1
            current_raw_idx += 1
    return "".join(raw_chars).upper(), raw_to_aligned


def _motif_matches_for_sequence(aligned_seq: str, pattern) -> List[int]:
    raw_seq, raw_to_aligned = _raw_to_aligned_map(aligned_seq)
    aligned_positions = []
    for match in pattern.finditer(raw_seq):
        start, end = match.span()  # [start, end)
        for raw_pos in range(start, end):
            if raw_pos in raw_to_aligned:
                aligned_positions.append(raw_to_aligned[raw_pos])
    return aligned_positions


def find_motif_matches(sequences: Dict[str, str], query: str) -> Dict[str, List[int]]:
    """
    Find columns in the alignment matching a motif query.
    Supports wildcards like 'X', '.', or '-' in the query.
    Example: 'RYY' or 'G.G' or 'G-P'
    """
    import re

    if not query.strip():
        return {}

    # Build the pattern character-by-character rather than compiling the
    # query as a raw regex: 'X'/'.'/'-' become a wildcard, every other
    # character is escaped literally. The query comes straight from an HTTP
    # request, so treating it as a real regex would let a caller inject
    # arbitrary regex syntax (catastrophic-backtracking quantifiers, etc.).
    clean_query = query.upper().replace(" ", "")
    pattern_str = "".join("." if ch in "X.-" else re.escape(ch) for ch in clean_query)
    try:
        pattern = re.compile(pattern_str)
    except re.error:
        return {}  # Invalid regex

    matches_map = {}
    for name, aligned_seq in sequences.items():
        positions = _motif_matches_for_sequence(aligned_seq, pattern)
        if positions:
            matches_map[name] = positions
    return matches_map


def _aligned_cols_to_raw_residues(seq: str, aligned_cols) -> List[int]:
    """Maps a set/list of 1-indexed aligned column numbers back to the
    1-indexed raw (gap-stripped) residue numbers they correspond to in
    this particular sequence."""
    cols = set(aligned_cols)
    raw_nums = []
    current_res = 1
    for i, char in enumerate(seq):
        if char != "-":
            if (i + 1) in cols:
                raw_nums.append(current_res)
            current_res += 1
    return raw_nums


def _empty_chain_mapping(sequences: Dict[str, str]) -> Dict[str, List[int]]:
    return {chr(ord("A") + i): [] for i in range(len(sequences))}


def _build_chain_mapping_from_matches(
    sequences: Dict[str, str], matches: Dict[str, list]
) -> Dict[str, List[int]]:
    all_headers = list(sequences.keys())
    final_mapping = _empty_chain_mapping(sequences)
    for name, cols in matches.items():
        chain_id = chr(ord("A") + all_headers.index(name))
        final_mapping[chain_id].extend(
            _aligned_cols_to_raw_residues(sequences[name], cols)
        )
    return final_mapping
