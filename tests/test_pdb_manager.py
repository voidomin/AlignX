from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest
from src.backend.pdb_manager import PDBManager


class TestPDBManager:

    @patch("src.backend.pdb_manager.Path.mkdir")
    def test_initialization(self, _, mock_config, temp_workspace):
        """Test if PDBManager initializes directories correctly."""
        # Patch the hardcoded paths in PDBManager __init__ to use temp_workspace
        manager = PDBManager(mock_config)
        assert manager.pdb_source == mock_config["pdb"]["source_url"]
        assert manager.timeout == 5

    @patch("src.backend.pdb_manager.Path.mkdir")
    def test_initialization_accepts_safe_session_id(self, _, mock_config):
        manager = PDBManager(mock_config, session_id="abc-123_XYZ")
        assert manager.session_id == "abc-123_XYZ"
        assert manager.raw_dir == Path("data/raw/abc-123_XYZ")

    @pytest.mark.parametrize(
        "bad_session_id",
        ["../../etc", "a/b", "a\\b", "..", "session id with spaces"],
    )
    def test_initialization_rejects_path_traversal_session_id(
        self, mock_config, bad_session_id
    ):
        """FastAPI's own endpoints already validate session_id (an
        attacker-controlled query param) before constructing a
        coordinator/PDBManager - this is a second, independent check so a
        future caller that skips that validation can't construct a path
        outside data/raw or data/cleaned."""
        with pytest.raises(ValueError, match="Invalid session_id"):
            PDBManager(mock_config, session_id=bad_session_id)

    def test_pdb_id_validation(self):
        """Test PDB ID validation logic."""
        assert PDBManager.validate_pdb_id("1A0J") is True
        assert (
            PDBManager.validate_pdb_id("4hhb") is True
        )  # Case insensitive in regex? Actually regex is stricter
        # The regex in code is r'^[0-9][A-Za-z0-9]{3}$'
        assert PDBManager.validate_pdb_id("1a0j") is True
        assert PDBManager.validate_pdb_id("invalid") is False
        assert PDBManager.validate_pdb_id("12345") is False
        assert PDBManager.validate_pdb_id("1A0") is False

    def test_pdb_id_validation_swissmodel_and_esmfold(self):
        """SM- (SWISS-MODEL, keyed by UniProt) and ESM- (ESM Atlas, keyed by
        MGYP accession) IDs must validate; malformed variants must not."""
        assert PDBManager.validate_pdb_id("SM-P69905") is True
        assert PDBManager.validate_pdb_id("sm-p69905") is True
        assert PDBManager.validate_pdb_id("SM-") is False
        assert PDBManager.validate_pdb_id("ESM-MGYP002537940442") is True
        assert PDBManager.validate_pdb_id("esm-mgyp002537940442") is True
        assert PDBManager.validate_pdb_id("ESM-P69905") is False  # not an MGYP id

    def test_detect_source(self):
        assert PDBManager.detect_source("4RLT") == "pdb"
        assert PDBManager.detect_source("AF-P69905-F1") == "alphafold"
        assert PDBManager.detect_source("SM-P69905") == "swissmodel"
        assert PDBManager.detect_source("ESM-MGYP002537940442") == "esmfold"
        assert PDBManager.detect_source("af-p69905-f1") == "alphafold"

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_download_pdb_success(self, mock_get, mock_config, temp_workspace):
        """Test successful PDB download."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "4"}
        mock_response.content = b"ATOM"
        mock_get.return_value = mock_response

        # Init manager
        manager = PDBManager(mock_config)
        # Override directories to use temp path
        manager.raw_dir = temp_workspace["raw"]

        success, msg, path = await manager.download_pdb("1A0J")

        assert success is True
        assert path.exists()
        assert path.name == "1a0j.pdb"
        assert path.read_bytes() == b"ATOM"

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_download_swissmodel_success(
        self, mock_get, mock_config, temp_workspace
    ):
        """SWISS-MODEL downloads must hit the UniProt-keyed repository URL
        and save real PDB bytes directly (no .cif conversion, unlike AlphaFold)."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b"ATOM SWISSMODEL"
        mock_get.return_value = mock_response

        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, msg, path = await manager.download_pdb("SM-P69905")

        assert success is True
        assert path.name == "sm-p69905.pdb"
        assert path.read_bytes() == b"ATOM SWISSMODEL"
        called_url = mock_get.call_args[0][0]
        assert (
            called_url == "https://swissmodel.expasy.org/repository/uniprot/P69905.pdb"
        )

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_download_esmfold_success(
        self, mock_get, mock_config, temp_workspace
    ):
        """ESM Atlas downloads must hit the MGYP-keyed fetchPredictedStructure
        URL and save real PDB bytes directly."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b"ATOM ESMFOLD"
        mock_get.return_value = mock_response

        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, msg, path = await manager.download_pdb("ESM-MGYP002537940442")

        assert success is True
        assert path.name == "esm-mgyp002537940442.pdb"
        assert path.read_bytes() == b"ATOM ESMFOLD"
        called_url = mock_get.call_args[0][0]
        assert (
            called_url
            == "https://api.esmatlas.com/fetchPredictedStructure/MGYP002537940442"
        )

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_download_swissmodel_not_found(
        self, mock_get, mock_config, temp_workspace
    ):
        """A 404 from SWISS-MODEL must be reported as a clean failure, not a crash."""
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, msg, path = await manager.download_pdb("SM-NOTREAL")

        assert success is False
        assert path is None
        assert "SWISS-MODEL" in msg

    def test_analyze_structure(self, mock_config, temp_workspace, dummy_pdb_content):
        """Test structure analysis (chain counting)."""
        manager = PDBManager(mock_config)

        # Create dummy file
        p = temp_workspace["raw"] / "test.pdb"
        p.write_text(dummy_pdb_content)

        info = manager.analyze_structure(p)

        assert info["num_models"] >= 1
        assert len(info["chains"]) == 1
        assert info["chains"][0]["id"] == "A"

    def test_clean_pdb(self, mock_config, temp_workspace, dummy_pdb_content):
        """Test cleaning function."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace["cleaned"]

        # Input file
        raw_file = temp_workspace["raw"] / "1test.pdb"
        raw_file.write_text(dummy_pdb_content)

        success, msg, cleaned_path = manager.clean_pdb(raw_file)

        assert success is True
        assert cleaned_path.exists()
        assert cleaned_path.parent == temp_workspace["cleaned"]

    def test_clean_pdb_prunes_low_plddt_for_alphafold_0_to_100_scale(
        self, mock_config, temp_workspace
    ):
        """AlphaFold structures encode per-residue pLDDT in the B-factor
        column on a 0-100 scale, so low-confidence residues (<50) should be
        pruned during cleaning."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace["cleaned"]

        content = (
            "ATOM      1  N   ALA A   1      11.104  13.203   7.334  1.00 90.00           N\n"
            "ATOM      2  CA  ALA A   1      12.104  14.203   8.334  1.00 90.00           C\n"
            "ATOM      3  N   GLY A   2      13.104  15.203   9.334  1.00 20.00           N\n"
            "ATOM      4  CA  GLY A   2      14.104  16.203  10.334  1.00 20.00           C\n"
            "TER"
        )
        raw_file = temp_workspace["raw"] / "af-p12345-f1.pdb"
        raw_file.write_text(content)

        success, msg, cleaned_path = manager.clean_pdb(raw_file)

        assert success is True
        cleaned_content = cleaned_path.read_text()
        assert "ALA" in cleaned_content
        assert "GLY" not in cleaned_content  # pLDDT 20 < 50, pruned

    def test_clean_pdb_detects_0_to_1_plddt_scale_for_esmfold(
        self, mock_config, temp_workspace
    ):
        """Regression test: ESM Atlas structures write per-residue confidence
        as a 0-1 fraction, not AlphaFold's 0-100 scale (e.g. a real ESMFold
        structure's max B-factor was 0.96). Naively comparing that against
        the same "< 50" threshold used for AlphaFold would strip every
        residue (0.96 < 50), leaving zero CA atoms and silently failing the
        whole structure - this must auto-detect the scale instead."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace["cleaned"]

        content = (
            "ATOM      1  N   ALA A   1      11.104  13.203   7.334  1.00  0.90           N\n"
            "ATOM      2  CA  ALA A   1      12.104  14.203   8.334  1.00  0.90           C\n"
            "ATOM      3  N   GLY A   2      13.104  15.203   9.334  1.00  0.20           N\n"
            "ATOM      4  CA  GLY A   2      14.104  16.203  10.334  1.00  0.20           C\n"
            "TER"
        )
        raw_file = temp_workspace["raw"] / "esm-mgyp002537940442.pdb"
        raw_file.write_text(content)

        success, msg, cleaned_path = manager.clean_pdb(raw_file)

        assert success is True
        cleaned_content = cleaned_path.read_text()
        assert "ALA" in cleaned_content  # 0.90 * 100 = 90 >= 50, kept
        assert "GLY" not in cleaned_content  # 0.20 * 100 = 20 < 50, pruned

    def test_clean_specific_chain(self, mock_config, temp_workspace):
        """Test cleaning a specific chain from a multi-chain PDB."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace["cleaned"]

        # Create multi-chain content with CA atoms
        multi_content = (
            "ATOM      1  N   ALA A   1      11.104  13.203   7.334  1.00 20.00           N\n"
            "ATOM      2  CA  ALA A   1      12.104  14.203   8.334  1.00 20.00           C\n"
            "TER\n"
            "ATOM      3  N   ALA B   1      21.104  23.203  17.334  1.00 20.00           N\n"
            "ATOM      4  CA  ALA B   1      22.104  24.203  18.334  1.00 20.00           C\n"
            "TER"
        )

        raw_file = temp_workspace["raw"] / "multi.pdb"
        raw_file.write_text(multi_content)

        # Clean only chain B
        success, msg, cleaned_path = manager.clean_pdb(raw_file, chain="B")

        assert success is True
        content = cleaned_path.read_text()
        assert "ALA B" in content
        assert "ALA A" not in content

    def test_build_residue_renumber_map(self, mock_config, temp_workspace):
        """Raw residue numbers (which can start anywhere, e.g. 49) must map to
        the 1-based sequential numbers clean_pdb() assigns, since ligand/
        interaction analysis runs against the raw PDB while the 3D viewer
        shows the cleaned, renumbered structure Mustang actually aligned."""
        manager = PDBManager(mock_config)

        content = (
            "HETATM    1  O   HOH A  48      10.000  10.000  10.000  1.00 20.00           O\n"
            "ATOM      2  N   ALA A  49      11.104  13.203   7.334  1.00 20.00           N\n"
            "ATOM      3  CA  ALA A  49      12.104  14.203   8.334  1.00 20.00           C\n"
            "ATOM      4  N   GLY A  50      13.104  15.203   9.334  1.00 20.00           N\n"
            "ATOM      5  CA  GLY A  50      14.104  16.203  10.334  1.00 20.00           C\n"
            "HETATM    6  C1  RET A 401      15.104  17.203  11.334  1.00 20.00           C\n"
            "TER"
        )
        raw_file = temp_workspace["raw"] / "renumber_test.pdb"
        raw_file.write_text(content)

        mapping = manager.build_residue_renumber_map(
            raw_file, chain="A", remove_heteroatoms=True, remove_water=True
        )

        # Water (48) and the ligand (401, no CA) are stripped; the two
        # standard residues become sequential 1, 2.
        assert mapping == {49: 1, 50: 2}

    def test_build_residue_renumber_map_detects_0_to_1_plddt_scale_for_esmfold(
        self, mock_config, temp_workspace
    ):
        """Same 0-1 vs 0-100 pLDDT scale detection as clean_pdb() - without
        it, an esm- file's low-confidence residues (all bfactor <= 1.0)
        would be misread as universally below the 50 threshold and pruned."""
        manager = PDBManager(mock_config)

        content = (
            "ATOM      1  N   ALA A   1      11.104  13.203   7.334  1.00  0.90           N\n"
            "ATOM      2  CA  ALA A   1      12.104  14.203   8.334  1.00  0.90           C\n"
            "ATOM      3  N   GLY A   2      13.104  15.203   9.334  1.00  0.20           N\n"
            "ATOM      4  CA  GLY A   2      14.104  16.203  10.334  1.00  0.20           C\n"
            "TER"
        )
        raw_file = temp_workspace["raw"] / "esm-mgyp002537940442.pdb"
        raw_file.write_text(content)

        mapping = manager.build_residue_renumber_map(
            raw_file, chain="A", remove_heteroatoms=True, remove_water=True
        )

        # Only ALA (0.90 * 100 = 90 >= 50) survives; GLY (20) is pruned.
        assert mapping == {1: 1}
