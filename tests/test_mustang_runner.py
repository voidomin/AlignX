from unittest.mock import patch, MagicMock
from pathlib import Path
from src.backend.mustang_runner import MustangRunner


class TestMustangRunner:

    def test_init(self, mock_config):
        """Test initialization of MustangRunner."""
        runner = MustangRunner(mock_config)
        assert runner.backend == "native"
        assert runner.timeout == 10

    @patch("shutil.which")
    def test_check_mustang_native_found(self, mock_which, mock_config):
        """Test detection of native mustang executable via check_installation."""
        mock_which.return_value = "/usr/bin/mustang"

        runner = MustangRunner(mock_config)
        found, msg = runner.check_installation()

        assert found is True
        assert "found" in msg.lower()

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_check_mustang_native_not_found(self, mock_run, mock_which, mock_config):
        """Test failure to detect native mustang."""
        mock_which.return_value = None
        mock_run.side_effect = Exception("Not found")

        runner = MustangRunner(mock_config)
        found, _ = runner._check_mustang()

        assert found is False

    @patch("shutil.which")
    def test_check_installation_is_cached_across_instances(
        self, mock_which, mock_config
    ):
        """check_installation() shells out (directly, or via a slow WSL
        subprocess) - a fresh MustangRunner is created per API request, so
        this must only actually run once per process, not once per request."""
        mock_which.return_value = "/usr/bin/mustang"

        runner1 = MustangRunner(mock_config)
        found1, msg1 = runner1.check_installation()
        assert mock_which.call_count == 1

        # A second, independent instance must reuse the cached result rather
        # than shelling out again.
        runner2 = MustangRunner(mock_config)
        found2, msg2 = runner2.check_installation()
        assert mock_which.call_count == 1
        assert (found2, msg2) == (found1, msg1)
        assert runner2.backend == "native"
        assert runner2.executable == "/usr/bin/mustang"

    def test_construct_command(self, mock_config):
        """Test command construction for alignment."""
        runner = MustangRunner(mock_config)
        runner.executable = "mustang"

        input_files = [Path("a.pdb"), Path("b.pdb")]
        output_dir = Path("results")

        cmd, _ = runner._construct_command(input_files, output_dir)

        assert cmd[0] == "mustang"
        assert "-F" in cmd
        assert "fasta" in cmd
        assert input_files[0].name in cmd

    @patch("src.backend.mustang_runner.os.chmod")
    def test_locate_compiled_binary_sets_owner_only_permissions(
        self, mock_chmod, mock_config, tmp_path
    ):
        """A SonarCloud-flagged security hotspot: the compiled binary must
        only be accessible to the owner (0o700), not group/other - nothing
        else on the (single-user) container ever needs to touch it."""
        runner = MustangRunner(mock_config)
        runner.is_windows = False

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "mustang-3.2.3").write_text("fake binary")

        found = runner._locate_compiled_binary(tmp_path)

        assert found is True
        mock_chmod.assert_called_once()
        assert mock_chmod.call_args[0][1] == 0o700

    @patch("src.backend.mustang_runner.subprocess.run")
    @patch("src.backend.mustang_runner.os.chmod")
    def test_verify_native_linux_binary_sets_owner_only_permissions(
        self, mock_chmod, mock_run, mock_config, tmp_path
    ):
        """Same reasoning as test_locate_compiled_binary_sets_owner_only_permissions
        - this is the sibling code path used when a binary from a fresh
        source compile is being verified directly, rather than located
        under bin/."""
        runner = MustangRunner(mock_config)
        bin_path = tmp_path / "mustang-3.2.3"
        bin_path.write_text("fake binary")

        found, _ = runner._verify_native_linux_binary(bin_path)

        assert found is True
        mock_chmod.assert_called_once_with(bin_path, 0o700)


class TestMustangRunnerValidation:
    """Tests for input validation and error handling."""

    def test_run_alignment_insufficient_files(self, mock_config, tmp_path):
        """Alignment should fail with fewer than 2 structures."""
        runner = MustangRunner(mock_config)
        single_file = tmp_path / "only_one.pdb"
        single_file.write_text(
            "ATOM      1  CA  ALA A   1       0.0   0.0   0.0  1.00  0.00\n"
        )

        success, msg, _ = runner.run_alignment([single_file], tmp_path / "out")
        assert success is False
        assert "at least 2" in msg.lower()

    def test_run_alignment_empty_list(self, mock_config, tmp_path):
        """Alignment should fail with empty input list."""
        runner = MustangRunner(mock_config)

        success, _, _ = runner.run_alignment([], tmp_path / "out")
        assert success is False

    @patch("subprocess.Popen")
    def test_exit_139_error_message(self, mock_popen, mock_config, tmp_path):
        """Exit code 139 should produce a divergence warning."""
        runner = MustangRunner(mock_config)
        runner.executable = "mustang"
        runner.use_wsl = False

        # Create dummy PDB files in output dir
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        for name in ["a.pdb", "b.pdb"]:
            (out_dir / name).write_text(
                "ATOM      1  CA  ALA A   1       0.0   0.0   0.0  1.00  0.00\n"
            )

        # Simulate Mustang segfault — no output files created
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.stdout.readline.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_process.returncode = 139
        mock_popen.return_value = mock_process

        success, msg, _ = runner.run_alignment(
            [out_dir / "a.pdb", out_dir / "b.pdb"], out_dir
        )

        assert success is False
        assert "divergence" in msg.lower()

    @patch("subprocess.Popen")
    def test_afasta_standardization(self, mock_popen, mock_config, tmp_path):
        """Test that .afasta is copied to .fasta when .fasta is missing."""
        runner = MustangRunner(mock_config)
        runner.executable = "mustang"
        runner.use_wsl = False

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        for name in ["a.pdb", "b.pdb"]:
            (out_dir / name).write_text(
                "ATOM      1  CA  ALA A   1       0.0   0.0   0.0  1.00  0.00\n"
            )

        # Simulate successful Mustang run
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.stdout.readline.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        (out_dir / "alignment.pdb").write_text(
            "ATOM      1  CA  ALA A   1       0.0   0.0   0.0\n"
        )
        (out_dir / "alignment.afasta").write_text(">a\nACDEF\n>b\nACDEF\n")

        success, _, _ = runner.run_alignment(
            [out_dir / "a.pdb", out_dir / "b.pdb"], out_dir
        )

        assert success is True
        assert (out_dir / "alignment.fasta").exists()
