"""
Mustang Pipeline - Automated Protein Structural Alignment

A comprehensive bioinformatics pipeline for multiple structural alignment
of protein families using Mustang, with phylogenetic analysis and visualization.

Author: Akash
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Akash"

from src.utils.config_loader import load_config
from src.utils.logger import setup_logger

__all__ = [
    "load_config",
    "setup_logger",
]
