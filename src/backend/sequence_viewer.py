"""
Sequence alignment visualization module.
Parses Mustang .afasta files and generates interactive HTML views.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from src.utils.logger import get_logger

logger = get_logger()

class SequenceViewer:
    def __init__(self):
        self.colors = {
            'identity': '#ff6b6b',  # Red for 100% match
            'high_similarity': '#feca57', # Yellow for high similarity
            'gap': '#dfe6e9',       # Grey for gaps
            'default': '#ffffff'    # White for others
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
            
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if line.startswith('>'):
                        if current_header:
                            sequences[current_header] = ''.join(current_seq)
                        current_header = line[1:].strip()  # Remove >
                        current_seq = []
                    else:
                        current_seq.append(line)
                
                # Add last sequence
                if current_header:
                    sequences[current_header] = ''.join(current_seq)
            
            return sequences
            
        except Exception as e:
            logger.error(f"Failed to parse AFASTA file: {e}")
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
            unique, counts = np.unique(residues, return_counts=True)
            max_count = np.max(counts)
            score = max_count / len(seq_list)
            
            # If gap is the most common, score should be low? Or handle separately.
            # Let's keep raw agreement score for now.
            scores.append(score)
            
        return scores

    def generate_html(self, sequences: Dict[str, str], conservation: List[float]) -> str:
        """
        Generate HTML/CSS for scrollable alignment view.
        """
        headers = list(sequences.keys())
        seqs = list(sequences.values())
        length = len(seqs[0])
        
        # Build Grid Rows
        rows_html = ""
        
        # 1. Header (Conservation Bar? Maybe later)
        
        # 2. Sequence Rows
        for header, seq in sequences.items():
            residues_html = ""
            for i, char in enumerate(seq):
                score = conservation[i]
                bg_color = self.colors['default']
                
                # Coloring logic
                if char == '-':
                    bg_color = self.colors['gap']
                elif score == 1.0: # Identical column
                    bg_color = self.colors['identity']
                elif score > 0.7: # High similarity
                    bg_color = self.colors['high_similarity']
                
                residues_html += f'<td style="background-color: {bg_color}; font-family: monospace; width: 20px; text-align: center;">{char}</td>'
                
            rows_html += f"""
            <tr>
                <td style="position: sticky; left: 0; background: white; z-index: 1; padding-right: 10px; font-weight: bold; border-right: 2px solid #ddd;">{header}</td>
                {residues_html}
            </tr>
            """
            
        # Consensus/Conservation Row
        cons_html = ""
        for score in conservation:
            symbol = "&nbsp;"
            if score == 1.0: symbol = "*"
            elif score > 0.7: symbol = ":"
            elif score > 0.5: symbol = "."
            
            cons_html += f'<td style="text-align: center; font-weight: bold;">{symbol}</td>'
            
        rows_html += f"""
        <tr style="background-color: #f1f2f6;">
            <td style="position: sticky; left: 0; background: #f1f2f6; border-right: 2px solid #ddd;">Consensus</td>
            {cons_html}
        </tr>
        """

        html = f"""
        <div style="overflow-x: auto; font-family: 'Courier New', monospace; font-size: 14px;">
            <table style="border-collapse: collapse; min-width: 100%;">
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
            matches = sum(1 for a, b in zip(s1, s2) if a == b and a != '-')
            length = len(s1)
            # Avoid division by zero
            if length == 0:
                continue
            # Identity = Matches / Total Alignment Length * 100
            identities.append((matches / length) * 100)
            
        return sum(identities) / len(identities) if identities else 0.0
