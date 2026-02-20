import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from src.backend.pdb_manager import PDBManager

class TestPDBManager:
    
    def test_initialization(self, mock_config, temp_workspace):
        """Test if PDBManager initializes directories correctly."""
        # Patch the hardcoded paths in PDBManager __init__ to use temp_workspace
        with patch.object(Path, 'mkdir') as mock_mkdir:
            manager = PDBManager(mock_config)
            assert manager.pdb_source == mock_config['pdb']['source_url']
            assert manager.timeout == 5

    def test_pdb_id_validation(self):
        """Test PDB ID validation logic."""
        assert PDBManager.validate_pdb_id("1A0J") is True
        assert PDBManager.validate_pdb_id("4hhb") is True  # Case insensitive in regex? Actually regex is stricter
        # The regex in code is r'^[0-9][A-Za-z0-9]{3}$'
        assert PDBManager.validate_pdb_id("1a0j") is True 
        assert PDBManager.validate_pdb_id("invalid") is False
        assert PDBManager.validate_pdb_id("12345") is False
        assert PDBManager.validate_pdb_id("1A0") is False

    @patch('src.backend.pdb_manager.requests.get')
    def test_download_pdb_success(self, mock_get, mock_config, temp_workspace):
        """Test successful PDB download."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1024'}
        mock_response.iter_content = lambda chunk_size: [b"ATOM"]
        mock_get.return_value = mock_response

        # Init manager
        manager = PDBManager(mock_config)
        # Override directories to use temp path
        manager.raw_dir = temp_workspace['raw']
        
        success, msg, path = manager.download_pdb("1A0J")
        
        assert success is True
        assert path.exists()
        assert path.name == "1A0J.pdb"
        
    def test_analyze_structure(self, mock_config, temp_workspace, dummy_pdb_content):
        """Test structure analysis (chain counting)."""
        manager = PDBManager(mock_config)
        
        # Create dummy file
        p = temp_workspace['raw'] / "test.pdb"
        p.write_text(dummy_pdb_content)
        
        info = manager.analyze_structure(p)
        
        assert info['num_models'] >= 1
        assert len(info['chains']) == 1
        assert info['chains'][0]['id'] == 'A'
        
    def test_clean_pdb(self, mock_config, temp_workspace, dummy_pdb_content):
        """Test cleaning function."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace['cleaned']
        
        # Input file
        raw_file = temp_workspace['raw'] / "1TEST.pdb"
        raw_file.write_text(dummy_pdb_content)
        
        success, msg, cleaned_path = manager.clean_pdb(raw_file)
        
        assert success is True
        assert cleaned_path.exists()
        assert cleaned_path.parent == temp_workspace['cleaned']

    def test_clean_specific_chain(self, mock_config, temp_workspace):
        """Test cleaning a specific chain from a multi-chain PDB."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace['cleaned']
        
        # Create multi-chain content
        multi_content = "ATOM      1  N   ALA A   1      11.104  13.203   7.334  1.00 20.00           N\n" \
                        "TER\n" \
                        "ATOM      2  N   ALA B   1      21.104  23.203  17.334  1.00 20.00           N\n" \
                        "TER"
        
        raw_file = temp_workspace['raw'] / "MULTI.pdb"
        raw_file.write_text(multi_content)
        
        # Clean only chain B
        success, msg, cleaned_path = manager.clean_pdb(raw_file, chain='B')
        
        assert success is True
        content = cleaned_path.read_text()
        assert "ALA B" in content
        assert "ALA A" not in content
