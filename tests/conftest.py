import pytest
import shutil
from pathlib import Path
from unittest.mock import MagicMock
from src.utils.logger import get_logger

# Disable logging during tests to keep output clean
logger = get_logger()
logger.disabled = True

@pytest.fixture
def mock_config():
    """Return a standard configuration dictionary for testing."""
    return {
        'app': {'name': 'Test App', 'max_proteins': 5},
        'pdb': {
            'source_url': 'https://files.rcsb.org/download/',
            'timeout': 5,
            'max_file_size_mb': 10
        },
        'mustang': {
            'backend': 'native',
            'executable_path': 'mustang',
            'timeout': 10
        },
        'filtering': {
            'remove_water': True,
            'remove_heteroatoms': True
        }
    }

@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with necessary subdirectories."""
    data_dir = tmp_path / "data"
    raw_dir = data_dir / "raw"
    cleaned_dir = data_dir / "cleaned"
    results_dir = tmp_path / "results"
    
    raw_dir.mkdir(parents=True)
    cleaned_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)
    
    return {
        'root': tmp_path,
        'raw': raw_dir,
        'cleaned': cleaned_dir,
        'results': results_dir
    }

@pytest.fixture
def dummy_pdb_content():
    """Return a minimal valid PDB string."""
    return (
        "ATOM      1  N   MET A   1      27.340  24.430   2.614  1.00  9.67           N  \n"
        "ATOM      2  CA  MET A   1      26.266  25.413   2.842  1.00 10.38           C  \n"
        "ATOM      3  C   MET A   1      26.913  26.639   3.531  1.00  9.62           C  \n"
        "ATOM      4  O   MET A   1      27.886  26.463   4.263  1.00 12.10           O  \n"
        "ATOM      5  CB  MET A   1      25.112  24.880   3.649  1.00 13.77           C  \n"
        "TER\n"
    )
