from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.backend.foldseek_runner import FoldseekRunner


def _mock_completed(returncode=0, stdout="", stderr=""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class TestCheckInstallation:

    def test_uses_configured_native_binary_path(self, mock_config):
        config = {
            **mock_config,
            "foldseek": {"local": {"binary_path": "/usr/bin/foldseek"}},
        }
        runner = FoldseekRunner(config)
        runner.is_windows = False
        runner.is_linux = True

        with patch("src.backend.foldseek_runner.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed()
            success, _ = runner.check_installation()

        assert success is True
        assert runner.executable == "/usr/bin/foldseek"
        assert runner.use_wsl is False

    def test_falls_back_to_native_path_lookup(self, mock_config):
        config = {**mock_config, "foldseek": {"local": {}}}
        runner = FoldseekRunner(config)
        runner.is_windows = False

        with patch(
            "src.backend.foldseek_runner.shutil.which",
            return_value="/usr/local/bin/foldseek",
        ), patch("src.backend.foldseek_runner.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed()
            success, _ = runner.check_installation()

        assert success is True
        assert runner.executable == "/usr/local/bin/foldseek"

    def test_falls_back_to_wsl_path_lookup_on_windows(self, mock_config):
        config = {**mock_config, "foldseek": {"local": {}}}
        runner = FoldseekRunner(config)
        runner.is_windows = True

        with patch(
            "src.backend.foldseek_runner.shutil.which", return_value=None
        ), patch("src.backend.foldseek_runner.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(
                returncode=0, stdout="/root/foldseek-local/foldseek/bin/foldseek\n"
            )
            success, _ = runner.check_installation()

        assert success is True
        assert runner.use_wsl is True
        assert runner.executable == "/root/foldseek-local/foldseek/bin/foldseek"

    def test_reports_failure_when_not_found_anywhere(self, mock_config):
        config = {**mock_config, "foldseek": {"local": {}}}
        runner = FoldseekRunner(config)
        runner.is_windows = False

        with patch("src.backend.foldseek_runner.shutil.which", return_value=None):
            success, msg = runner.check_installation()

        assert success is False
        assert "not found" in msg.lower()

    def test_caches_installation_check_across_instances(self, mock_config):
        config = {
            **mock_config,
            "foldseek": {"local": {"binary_path": "/usr/bin/foldseek"}},
        }

        with patch("src.backend.foldseek_runner.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed()
            FoldseekRunner(config).check_installation()
            FoldseekRunner(config).check_installation()

        assert mock_run.call_count == 1


class TestSearchAgainstDirectory:

    def test_returns_failure_when_not_installed(self, mock_config, tmp_path):
        config = {**mock_config, "foldseek": {"local": {}}}
        runner = FoldseekRunner(config)
        runner.is_windows = False

        with patch("src.backend.foldseek_runner.shutil.which", return_value=None):
            success, _, hits = runner.search_against_directory(
                tmp_path / "query.pdb", tmp_path / "db", tmp_path / "tmp"
            )

        assert success is False
        assert hits == []

    def test_parses_tsv_results_into_hit_dicts(self, mock_config, tmp_path):
        config = {
            **mock_config,
            "foldseek": {"local": {"binary_path": "/usr/bin/foldseek"}},
        }
        runner = FoldseekRunner(config)
        runner.is_windows = False

        def fake_run(cmd, **kwargs):
            if cmd == ["/usr/bin/foldseek"]:
                return _mock_completed()
            # The easy-search invocation - write a result.tsv where the
            # runner expects it (5th positional arg is the result path).
            result_path = Path(cmd[4])
            result_path.write_text(
                "query\t2lyz\t2.735E-23\t1.000\t1.000\t129\t1\t129\t1\t129\n"
                "query\t1cdk_B\t6.613E+00\t0.000\t0.041\t24\t39\t59\t38\t61\n"
            )
            return _mock_completed()

        with patch("src.backend.foldseek_runner.subprocess.run", side_effect=fake_run):
            success, _, hits = runner.search_against_directory(
                tmp_path / "query.pdb", tmp_path / "db", tmp_path / "tmp"
            )

        assert success is True
        assert len(hits) == 2
        assert hits[0]["target"] == "2lyz"
        assert hits[0]["eval"] == pytest.approx(2.735e-23)
        assert hits[0]["prob"] == pytest.approx(1.0)
        assert hits[0]["seqId"] == pytest.approx(100.0)
        assert hits[1]["target"] == "1cdk_B"
        assert hits[1]["seqId"] == pytest.approx(4.1)

    def test_returns_failure_on_nonzero_exit(self, mock_config, tmp_path):
        config = {
            **mock_config,
            "foldseek": {"local": {"binary_path": "/usr/bin/foldseek"}},
        }
        runner = FoldseekRunner(config)
        runner.is_windows = False

        def fake_run(cmd, **kwargs):
            if cmd == ["/usr/bin/foldseek"]:
                return _mock_completed()
            return _mock_completed(returncode=1, stderr="easy-search: bad input")

        with patch("src.backend.foldseek_runner.subprocess.run", side_effect=fake_run):
            success, msg, hits = runner.search_against_directory(
                tmp_path / "query.pdb", tmp_path / "db", tmp_path / "tmp"
            )

        assert success is False
        assert "bad input" in msg
        assert hits == []

    def test_skips_malformed_result_rows(self, mock_config, tmp_path):
        config = {
            **mock_config,
            "foldseek": {"local": {"binary_path": "/usr/bin/foldseek"}},
        }
        runner = FoldseekRunner(config)
        runner.is_windows = False

        def fake_run(cmd, **kwargs):
            if cmd == ["/usr/bin/foldseek"]:
                return _mock_completed()
            result_path = Path(cmd[4])
            result_path.write_text(
                "query\t2lyz\t2.735E-23\t1.000\t1.000\t129\t1\t129\t1\t129\n"
                "this-line-has-too-few-columns\n"
            )
            return _mock_completed()

        with patch("src.backend.foldseek_runner.subprocess.run", side_effect=fake_run):
            success, _, hits = runner.search_against_directory(
                tmp_path / "query.pdb", tmp_path / "db", tmp_path / "tmp"
            )

        assert success is True
        assert len(hits) == 1
        assert hits[0]["target"] == "2lyz"
