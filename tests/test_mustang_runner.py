import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.backend.mustang_runner import MustangRunner

class TestMustangRunner:
    
    def test_init(self, mock_config):
        """Test initialization of MustangRunner."""
        runner = MustangRunner(mock_config)
        assert runner.backend == 'native'
        assert runner.timeout == 10
        
    @patch('shutil.which')
    def test_check_mustang_native_found(self, mock_which, mock_config):
        """Test detection of native mustang executable."""
        mock_which.return_value = "/usr/bin/mustang"
        
        runner = MustangRunner(mock_config)
        found, msg = runner._check_mustang()
        
        assert found is True
        assert "found" in msg.lower()
        
    @patch('shutil.which')
    @patch('subprocess.run')
    def test_check_mustang_native_not_found(self, mock_run, mock_which, mock_config):
        """Test failure to detect native mustang."""
        mock_which.return_value = None
        mock_run.side_effect = Exception("Not found")
        
        runner = MustangRunner(mock_config)
        found, msg = runner._check_mustang()
        
        assert found is False
        
    def test_construct_command(self, mock_config):
        """Test command construction for alignment."""
        runner = MustangRunner(mock_config)
        runner.executable = "mustang"
        
        input_files = [Path("a.pdb"), Path("b.pdb")]
        output_dir = Path("results")
        
        cmd, cwd = runner._construct_command(input_files, output_dir)
        
        assert cmd[0] == "mustang"
        assert "-F" in cmd
        assert "fasta" in cmd
        assert input_files[0].name in cmd
