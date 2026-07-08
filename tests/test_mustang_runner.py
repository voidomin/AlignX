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


class TestConvertToWslPath:
    def test_converts_windows_drive_path_to_wsl_mount(self, mock_config):
        runner = MustangRunner(mock_config)
        result = runner._convert_to_wsl_path(Path("C:/Users/test/mustang"))
        assert result == "/mnt/c/Users/test/mustang"

    def test_lowercases_the_drive_letter(self, mock_config):
        runner = MustangRunner(mock_config)
        result = runner._convert_to_wsl_path(Path("D:/data/file.pdb"))
        assert result.startswith("/mnt/d/")


class TestEnsureFastaExists:
    def test_noop_when_fasta_already_exists(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        fasta = tmp_path / "alignment.fasta"
        fasta.write_text("original")

        runner._ensure_fasta_exists(tmp_path, fasta)

        assert fasta.read_text() == "original"

    def test_copies_from_afasta_when_fasta_missing(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        (tmp_path / "alignment.afasta").write_text(">a\nACDEF\n")
        fasta = tmp_path / "alignment.fasta"

        runner._ensure_fasta_exists(tmp_path, fasta)

        assert fasta.exists()
        assert fasta.read_text() == ">a\nACDEF\n"

    def test_falls_back_to_any_fasta_glob_match(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        (tmp_path / "results.fasta").write_text(">x\nACDEF\n")
        fasta = tmp_path / "alignment.fasta"

        runner._ensure_fasta_exists(tmp_path, fasta)

        assert fasta.exists()

    def test_leaves_fasta_missing_when_nothing_to_copy_from(
        self, mock_config, tmp_path
    ):
        runner = MustangRunner(mock_config)
        fasta = tmp_path / "alignment.fasta"

        runner._ensure_fasta_exists(tmp_path, fasta)

        assert not fasta.exists()


class TestCheckNativeInstallation:
    def test_returns_false_when_no_mustang_path_set(self, mock_config):
        runner = MustangRunner(mock_config)
        found, msg = runner._check_native_installation()
        assert found is False

    @patch("subprocess.run")
    def test_returns_true_when_binary_runs_successfully(
        self, mock_run, mock_config, tmp_path
    ):
        runner = MustangRunner(mock_config)
        fake_binary = tmp_path / "mustang"
        fake_binary.write_text("fake")
        runner.mustang_path = fake_binary

        found, msg = runner._check_native_installation()

        assert found is True
        assert runner.use_wsl is False

    def test_returns_false_when_path_does_not_exist(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        runner.mustang_path = tmp_path / "does_not_exist"

        found, msg = runner._check_native_installation()

        assert found is False


class TestCheckWslSystemInstallation:
    def test_returns_false_on_non_windows(self, mock_config):
        runner = MustangRunner(mock_config)
        runner.is_windows = False
        found, msg = runner._check_wsl_system_installation()
        assert found is False

    @patch("subprocess.run")
    def test_returns_true_when_wsl_which_succeeds(self, mock_run, mock_config):
        runner = MustangRunner(mock_config)
        runner.is_windows = True
        mock_run.return_value = MagicMock(returncode=0)

        found, msg = runner._check_wsl_system_installation()

        assert found is True
        assert runner.use_wsl is True
        assert runner.executable == "mustang"

    @patch("subprocess.run")
    def test_returns_false_when_wsl_which_fails(self, mock_run, mock_config):
        runner = MustangRunner(mock_config)
        runner.is_windows = True
        mock_run.return_value = MagicMock(returncode=1)

        found, msg = runner._check_wsl_system_installation()

        assert found is False


class TestVerifyWslBinary:
    @patch("subprocess.run")
    def test_returns_true_when_binary_is_runnable(
        self, mock_run, mock_config, tmp_path
    ):
        runner = MustangRunner(mock_config)
        mock_run.return_value = MagicMock(returncode=0)
        bin_path = tmp_path / "mustang"

        found, msg = runner._verify_wsl_binary(bin_path)

        assert found is True
        assert runner.use_wsl is True

    @patch("subprocess.run")
    def test_returns_false_when_wsl_reports_command_not_found(
        self, mock_run, mock_config, tmp_path
    ):
        runner = MustangRunner(mock_config)
        mock_run.return_value = MagicMock(returncode=127)

        found, msg = runner._verify_wsl_binary(tmp_path / "mustang")

        assert found is False


class TestCheckCompiledBinary:
    def test_returns_false_when_build_dir_missing(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        runner._base_dir = tmp_path

        found, msg = runner._check_compiled_binary()

        assert found is False

    def test_returns_false_when_no_binary_glob_match(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        runner._base_dir = tmp_path
        (tmp_path / "mustang_build").mkdir()

        found, msg = runner._check_compiled_binary()

        assert found is False

    @patch("src.backend.mustang_runner.os.chmod")
    @patch("subprocess.run")
    def test_delegates_to_native_verification_on_linux(
        self, mock_run, mock_chmod, mock_config, tmp_path
    ):
        runner = MustangRunner(mock_config)
        runner.is_windows = False
        runner._base_dir = tmp_path
        bin_dir = tmp_path / "mustang_build" / "src" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "mustang-3.2.3").write_text("fake")

        found, msg = runner._check_compiled_binary()

        assert found is True
        assert "Native Linux" in msg


class TestCheckMustang:
    def test_prefers_native_over_wsl_and_compiled(self, mock_config):
        runner = MustangRunner(mock_config)
        with patch.object(
            runner, "_check_native_installation", return_value=(True, "native ok")
        ), patch.object(runner, "_check_wsl_system_installation") as wsl, patch.object(
            runner, "_check_compiled_binary"
        ) as compiled:
            found, msg = runner._check_mustang()

        assert found is True
        assert msg == "native ok"
        wsl.assert_not_called()
        compiled.assert_not_called()

    def test_falls_through_to_compiled_binary_when_others_fail(self, mock_config):
        runner = MustangRunner(mock_config)
        with patch.object(
            runner, "_check_native_installation", return_value=(False, "")
        ), patch.object(
            runner, "_check_wsl_system_installation", return_value=(False, "")
        ), patch.object(
            runner, "_check_compiled_binary", return_value=(True, "compiled ok")
        ):
            found, msg = runner._check_mustang()

        assert found is True
        assert msg == "compiled ok"

    def test_returns_false_when_all_strategies_fail(self, mock_config):
        runner = MustangRunner(mock_config)
        with patch.object(
            runner, "_check_native_installation", return_value=(False, "")
        ), patch.object(
            runner, "_check_wsl_system_installation", return_value=(False, "")
        ), patch.object(
            runner, "_check_compiled_binary", return_value=(False, "")
        ):
            found, msg = runner._check_mustang()

        assert found is False
        assert "not found" in msg.lower()


class TestUpdateExecutableFromCheck:
    def test_native_backend_uses_mustang_path_directly(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        runner.use_wsl = False
        runner.mustang_path = tmp_path / "mustang"

        runner._update_executable_from_check()

        assert runner.backend == "native"
        assert runner.executable == str(tmp_path / "mustang")

    def test_wsl_backend_with_bare_command_stays_bare(self, mock_config):
        runner = MustangRunner(mock_config)
        runner.use_wsl = True
        runner.mustang_path = Path("mustang")

        runner._update_executable_from_check()

        assert runner.backend == "wsl"
        assert runner.executable == "mustang"

    def test_wsl_backend_with_real_path_gets_converted(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        runner.use_wsl = True
        runner.mustang_path = tmp_path / "mustang"

        runner._update_executable_from_check()

        assert runner.backend == "wsl"
        assert runner.executable.startswith("/mnt/")


class TestDeepWslCheck:
    @patch("subprocess.run")
    def test_finds_mustang_in_wsl_output(self, mock_run, mock_config):
        runner = MustangRunner(mock_config)
        # backend only gets promoted to "wsl" when it started as "auto" or
        # "bio3d" - mock_config's fixed "native" backend is left untouched
        # deliberately, so set "auto" here to exercise that promotion path.
        runner.backend = "auto"
        mock_run.return_value = MagicMock(returncode=0, stdout=b"/usr/bin/mustang\n")

        found, msg = runner._deep_wsl_check()

        assert found is True
        assert runner.use_wsl is True
        assert runner.backend == "wsl"

    @patch("subprocess.run")
    def test_returns_false_when_mustang_not_in_output(self, mock_run, mock_config):
        runner = MustangRunner(mock_config)
        mock_run.return_value = MagicMock(returncode=1, stdout=b"")

        found, msg = runner._deep_wsl_check()

        assert found is False


class TestPerformInstallationCheck:
    @patch("shutil.which")
    def test_finds_mustang_on_path_first(self, mock_which, mock_config):
        runner = MustangRunner(mock_config)
        mock_which.return_value = "/usr/bin/mustang"

        found, msg = runner._perform_installation_check()

        assert found is True
        assert runner.backend == "native"

    @patch("shutil.which")
    def test_falls_back_to_compilation_when_nothing_found(
        self, mock_which, mock_config
    ):
        runner = MustangRunner(mock_config)
        runner.is_windows = False
        mock_which.return_value = None

        with patch.object(
            runner, "_check_mustang", return_value=(False, "")
        ), patch.object(runner, "_compile_from_source", return_value=False):
            found, msg = runner._perform_installation_check()

        assert found is False
        assert "neither" in msg.lower()

    @patch("shutil.which")
    def test_succeeds_after_compiling_from_source(self, mock_which, mock_config):
        runner = MustangRunner(mock_config)
        runner.is_windows = False
        mock_which.return_value = None

        with patch.object(
            runner, "_check_mustang", return_value=(False, "")
        ), patch.object(
            runner, "_compile_from_source", return_value=True
        ), patch.object(
            runner, "_update_executable_from_check"
        ):
            # _check_mustang is called twice: once before compiling (fails),
            # once after (succeeds) - side_effect models that sequence.
            with patch.object(
                runner,
                "_check_mustang",
                side_effect=[(False, ""), (True, "compiled ok")],
            ):
                found, msg = runner._perform_installation_check()

        assert found is True
        assert "Compiled Mustang binary" in msg


class TestFallbackExecutable:
    def test_uses_wsl_when_windows_and_wsl_available(self, mock_config):
        runner = MustangRunner(mock_config)
        runner.is_windows = True
        with patch("shutil.which", return_value="wsl"):
            runner._fallback_executable()
        assert runner.use_wsl is True
        assert runner.executable == "mustang"

    def test_uses_bare_command_when_not_windows(self, mock_config):
        runner = MustangRunner(mock_config)
        runner.is_windows = False
        with patch("shutil.which", return_value=None):
            runner._fallback_executable()
        assert runner.executable == "mustang"


class TestRunAlignmentValidation:
    def test_requires_at_least_two_structures(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        success, msg, result = runner.run_alignment([tmp_path / "a.pdb"], tmp_path)
        assert success is False
        assert "at least 2" in msg.lower()
        assert result is None


class TestFinalizeAlignmentOutput:
    def test_success_when_alignment_pdb_exists(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)
        (tmp_path / "alignment.pdb").write_text("ATOM")
        (tmp_path / "alignment.fasta").write_text(">a\nACDEF\n")

        success, msg, result_dir = runner._finalize_alignment_output(tmp_path, 0)

        assert success is True
        assert result_dir == tmp_path

    def test_failure_when_alignment_pdb_missing(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)

        success, msg, result_dir = runner._finalize_alignment_output(tmp_path, 1)

        assert success is False
        assert result_dir is None

    def test_exit_code_139_mentions_structural_divergence(self, mock_config, tmp_path):
        runner = MustangRunner(mock_config)

        success, msg, result_dir = runner._finalize_alignment_output(tmp_path, 139)

        assert success is False
        assert "divergence" in msg.lower()


class TestStreamProcessOutput:
    def test_collects_stdout_lines_until_process_exits(self, mock_config):
        # poll() is only consulted once readline() returns an empty string
        # (i.e. no more buffered output right now) - two real lines, then
        # one "still running" empty read, then one "exited" empty read.
        runner = MustangRunner(mock_config)
        process = MagicMock()
        process.stdout.readline.side_effect = ["line1\n", "line2\n", "", ""]
        process.poll.side_effect = [None, 0]
        process.stderr.read.return_value = "some stderr"

        stdout, stderr = runner._stream_process_output(process, timeout=5)

        assert stdout == "line1\nline2\n"
        assert stderr == "some stderr"

    def test_raises_timeout_error_when_exceeded(self, mock_config):
        runner = MustangRunner(mock_config)
        process = MagicMock()
        process.stdout.readline.return_value = ""
        process.poll.return_value = None

        with patch("time.time", side_effect=[0, 100]):
            try:
                runner._stream_process_output(process, timeout=5)
                assert False, "expected TimeoutError"
            except TimeoutError:
                pass
        process.kill.assert_called_once()
