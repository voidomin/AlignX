import pytest
from src.utils.logger import get_logger

# Disable logging during tests to keep output clean
logger = get_logger()
logger.disabled = True


@pytest.fixture(autouse=True)
def reset_mustang_installation_cache():
    """MustangRunner caches its installation check at the class level (see
    mustang_runner.py) since it's expensive and shouldn't re-run per-request
    in production. Reset it around every test so a real check_installation()
    call in one test can't leak a stale cached result into another test that
    expects different mocked behavior."""
    from src.backend.mustang_runner import MustangRunner

    MustangRunner._cached_installation = None
    yield
    MustangRunner._cached_installation = None


@pytest.fixture(autouse=True)
def reset_foldseek_runner_installation_cache():
    """Same rationale as reset_mustang_installation_cache above, for
    FoldseekRunner's equivalent class-level installation cache."""
    from src.backend.foldseek_runner import FoldseekRunner

    FoldseekRunner._cached_installation = None
    yield
    FoldseekRunner._cached_installation = None


@pytest.fixture
def mock_config():
    """Return a standard configuration dictionary for testing."""
    return {
        "app": {"name": "Test App", "max_proteins": 5},
        "pdb": {
            "source_url": "https://files.rcsb.org/download/",
            "timeout": 5,
            "max_file_size_mb": 10,
        },
        "mustang": {"backend": "native", "executable_path": "mustang", "timeout": 10},
        "filtering": {"remove_water": True, "remove_heteroatoms": True},
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
        "root": tmp_path,
        "raw": raw_dir,
        "cleaned": cleaned_dir,
        "results": results_dir,
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


# Shared minimal mmCIF atom_site loop header (matches a real AlphaFold-
# sourced download's column set) - used by every test that needs a real
# .cif fixture (test_pdb_manager.py, test_ligand_analyzer.py,
# test_interface_analyzer.py) so the ~20-line header isn't duplicated
# verbatim across files.
MINIMAL_CIF_HEADER = (
    "data_test\n"
    "loop_\n"
    "_atom_site.group_PDB\n"
    "_atom_site.id\n"
    "_atom_site.type_symbol\n"
    "_atom_site.label_atom_id\n"
    "_atom_site.label_alt_id\n"
    "_atom_site.label_comp_id\n"
    "_atom_site.label_asym_id\n"
    "_atom_site.label_entity_id\n"
    "_atom_site.label_seq_id\n"
    "_atom_site.pdbx_PDB_ins_code\n"
    "_atom_site.Cartn_x\n"
    "_atom_site.Cartn_y\n"
    "_atom_site.Cartn_z\n"
    "_atom_site.occupancy\n"
    "_atom_site.B_iso_or_equiv\n"
    "_atom_site.pdbx_formal_charge\n"
    "_atom_site.auth_seq_id\n"
    "_atom_site.auth_asym_id\n"
    "_atom_site.pdbx_PDB_model_num\n"
)
