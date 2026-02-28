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
