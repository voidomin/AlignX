from unittest.mock import patch, AsyncMock
import pytest
from src.backend.pdb_manager import PDBManager
from src.backend.mustang_runner import MustangRunner


class TestPipelineIntegration:

    @pytest.mark.asyncio
    async def test_download_and_clean_integration(
        self, mock_config, temp_workspace, dummy_pdb_content
    ):
        """
        Integration test: Download -> Clean.
        Verifies that PDBManager correctly handles the flow from raw data to cleaned files.
        """
        manager = PDBManager(mock_config)
        # Override data directories
        manager.raw_dir = temp_workspace["raw"]
        manager.cleaned_dir = temp_workspace["cleaned"]

        # Mock the async download to avoid network calls
        dummy_file = temp_workspace["raw"] / "1dum.pdb"
        dummy_file.write_text(dummy_pdb_content)

        with patch.object(
            manager, "download_pdb", new_callable=AsyncMock
        ) as mock_dl:
            mock_dl.return_value = (True, "Downloaded", dummy_file)

            # 1. Download (Mocked)
            success, msg, raw_path = await manager.download_pdb("1DUM")
            assert success is True
            assert raw_path.exists()

            # 2. Clean
            success, msg, cleaned_path = manager.clean_pdb(raw_path)
            assert success is True
            assert cleaned_path.exists()
            assert cleaned_path.parent == temp_workspace["cleaned"]

    def test_mustang_execution_command(self, mock_config, temp_workspace):
        """
        Integration test: Verify MustangRunner constructs valid commands for a set of files.
        """
        runner = MustangRunner(mock_config)
        runner.executable = "mustang"

        # Create dummy input files
        files = [
            temp_workspace["cleaned"] / "protein1.pdb",
            temp_workspace["cleaned"] / "protein2.pdb",
        ]
        for f in files:
            f.touch()

        output_dir = temp_workspace["results"]

        # Check command construction
        cmd, cwd = runner._construct_command(files, output_dir)

        assert len(cmd) > 5
        assert files[0].name in cmd
        assert files[1].name in cmd
        assert "-o" in cmd
        assert "-F" in cmd
