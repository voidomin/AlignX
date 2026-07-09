from pathlib import Path
from unittest.mock import patch, AsyncMock

import numpy as np
import pandas as pd
import pytest

from src.backend.coordinator import (
    AnalysisCoordinator,
    sanitize_for_json,
    _sanitize_json_key,
)


class TestSanitizeJsonKey:
    def test_numpy_integer_key_becomes_python_int(self):
        key = _sanitize_json_key(np.int64(5))
        assert key == 5
        assert isinstance(key, int)

    def test_numpy_floating_key_becomes_python_float(self):
        key = _sanitize_json_key(np.float32(1.5))
        assert key == pytest.approx(1.5)
        assert isinstance(key, float)

    def test_path_key_becomes_string(self):
        assert _sanitize_json_key(Path("results/run_1")) == str(Path("results/run_1"))

    def test_other_non_primitive_key_becomes_string(self):
        class Weird:
            def __str__(self):
                return "weird-key"

        assert _sanitize_json_key(Weird()) == "weird-key"

    def test_primitive_keys_pass_through_unchanged(self):
        assert _sanitize_json_key("a") == "a"
        assert _sanitize_json_key(1) == 1
        assert _sanitize_json_key(True) is True
        assert _sanitize_json_key(None) is None


class TestSanitizeForJson:
    def test_tuple_becomes_list(self):
        assert sanitize_for_json((1, 2, 3)) == [1, 2, 3]

    def test_numpy_floating_becomes_python_float(self):
        result = sanitize_for_json(np.float64(3.5))
        assert result == pytest.approx(3.5)
        assert isinstance(result, float)

    def test_numpy_integer_becomes_python_int(self):
        result = sanitize_for_json(np.int32(7))
        assert result == 7
        assert isinstance(result, int)

    def test_numpy_array_becomes_list(self):
        assert sanitize_for_json(np.array([1, 2, 3])) == [1, 2, 3]

    def test_dataframe_becomes_split_dict(self):
        df = pd.DataFrame({"a": [1, 2]}, index=["x", "y"])
        result = sanitize_for_json(df)
        assert result["columns"] == ["a"]
        assert result["index"] == ["x", "y"]
        assert result["data"] == [[1], [2]]

    def test_path_becomes_string(self):
        assert sanitize_for_json(Path("a/b")) == str(Path("a/b"))

    def test_dict_keys_are_sanitized_too(self):
        result = sanitize_for_json({np.int64(1): "value"})
        assert result == {1: "value"}

    def test_plain_value_passes_through(self):
        assert sanitize_for_json("hello") == "hello"
        assert sanitize_for_json(42) == 42


def _write_alignment_fixture(result_dir: Path):
    """A minimal but real 2-structure Mustang-shaped output directory:
    real RMSD data (via .rms_rot), a real 2-model PDB, and a matching
    aligned FASTA - enough for process_result_directory to run its full,
    real pipeline (heatmap, stats, phylo tree, sequence view, RMSF)
    without needing an actual Mustang binary."""
    result_dir.mkdir(parents=True, exist_ok=True)

    (result_dir / "alignment.rms_rot").write_text(
        "RMSD matrix\n1 | 0.00  1.50\n2 | 1.50  0.00\n"
    )

    lines = []
    for model_idx, offset in enumerate([0.0, 1.5], start=1):
        lines.append(f"MODEL     {model_idx}")
        for i, base in enumerate([0.0, 5.0, 10.0], start=1):
            lines.append(
                f"ATOM  {i:5d}  CA  ALA A{i:4d}    {base + offset:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00           C"
            )
        lines.append("ENDMDL")
    lines.append("END\n")
    (result_dir / "alignment.pdb").write_text("\n".join(lines))
    (result_dir / "alignment.fasta").write_text(">4RLT\nAAA\n>3UG9\nAAA\n")


def test_run_full_pipeline_fails_loudly_when_a_structure_cannot_be_cleaned(
    mock_config, tmp_path
):
    """A structure that fails clean_pdb() (e.g. the ESM Atlas 0-1 pLDDT scale
    bug, where every residue was wrongly pruned) must abort the whole
    alignment with a clear error - not silently continue with fewer
    structures than requested, which would produce a misleading result
    (the RMSD matrix, chain_selection, etc. would still look like all
    requested structures were included)."""
    with patch(
        "src.backend.coordinator.MustangRunner.check_installation",
        return_value=(True, "ok"),
    ), patch(
        "src.backend.coordinator.PDBManager.batch_download", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.backend.coordinator.PDBManager.analyze_structure"
    ) as mock_analyze, patch(
        "src.backend.coordinator.PDBManager.clean_pdb"
    ) as mock_clean, patch(
        "src.backend.coordinator.MustangRunner.run_alignment"
    ) as mock_align:
        good_path = tmp_path / "4rlt.pdb"
        bad_path = tmp_path / "esm-mgyp002537940442.pdb"
        good_path.write_text("ATOM")
        bad_path.write_text("ATOM")

        mock_download.return_value = {
            "4RLT": (True, "ok", good_path),
            "ESM-MGYP002537940442": (True, "ok", bad_path),
        }
        mock_analyze.return_value = {"chains": [{"id": "A", "residue_count": 100}]}

        def clean_side_effect(pdb_file, **kwargs):
            if "esm" in pdb_file.name.lower():
                return False, "0 Alpha Carbon (CA) atoms", None
            return True, "ok", tmp_path / f"cleaned_{pdb_file.name}"

        mock_clean.side_effect = clean_side_effect

        coordinator = AnalysisCoordinator(mock_config)
        success, msg, results = coordinator.run_full_pipeline(
            ["4RLT", "ESM-MGYP002537940442"], output_dir=tmp_path / "out"
        )

        assert success is False
        assert "ESM-MGYP002537940442" in msg
        assert results is None
        # Mustang must never be invoked with a partial structure set.
        mock_align.assert_not_called()


def test_init_warns_but_does_not_raise_when_mustang_not_installed(mock_config):
    """A coordinator must still construct successfully even when Mustang
    isn't available - callers (e.g. the /health endpoint) rely on being
    able to report the failure rather than the constructor itself raising."""
    with patch(
        "src.backend.coordinator.MustangRunner.check_installation",
        return_value=(False, "mustang binary not found"),
    ):
        coordinator = AnalysisCoordinator(mock_config)
        assert coordinator is not None


def test_run_full_pipeline_fails_when_mustang_alignment_fails(mock_config, tmp_path):
    with patch(
        "src.backend.coordinator.MustangRunner.check_installation",
        return_value=(True, "ok"),
    ), patch(
        "src.backend.coordinator.PDBManager.batch_download", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.backend.coordinator.PDBManager.analyze_structure",
        return_value={"chains": []},
    ), patch(
        "src.backend.coordinator.PDBManager.clean_pdb"
    ) as mock_clean, patch(
        "src.backend.coordinator.MustangRunner.run_alignment"
    ) as mock_align:
        pdb_file = tmp_path / "4rlt.pdb"
        pdb_file.write_text("ATOM")
        mock_download.return_value = {"4RLT": (True, "ok", pdb_file)}
        mock_clean.return_value = (True, "ok", pdb_file)
        mock_align.return_value = (False, "Mustang exited with code 139", None)

        coordinator = AnalysisCoordinator(mock_config)
        success, msg, results = coordinator.run_full_pipeline(
            ["4RLT"], output_dir=tmp_path / "out"
        )

        assert success is False
        assert "Mustang exited with code 139" in msg
        assert results is None


def test_run_full_pipeline_fails_when_result_processing_fails(mock_config, tmp_path):
    with patch(
        "src.backend.coordinator.MustangRunner.check_installation",
        return_value=(True, "ok"),
    ), patch(
        "src.backend.coordinator.PDBManager.batch_download", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.backend.coordinator.PDBManager.analyze_structure",
        return_value={"chains": []},
    ), patch(
        "src.backend.coordinator.PDBManager.clean_pdb"
    ) as mock_clean, patch(
        "src.backend.coordinator.MustangRunner.run_alignment"
    ) as mock_align, patch.object(
        AnalysisCoordinator, "process_result_directory", return_value=None
    ):
        pdb_file = tmp_path / "4rlt.pdb"
        pdb_file.write_text("ATOM")
        mock_download.return_value = {"4RLT": (True, "ok", pdb_file)}
        mock_clean.return_value = (True, "ok", pdb_file)
        mock_align.return_value = (True, "ok", tmp_path / "out")

        coordinator = AnalysisCoordinator(mock_config)
        success, msg, results = coordinator.run_full_pipeline(
            ["4RLT"], output_dir=tmp_path / "out"
        )

        assert success is False
        assert "Failed to process result directory" in msg
        assert results is None


def test_run_full_pipeline_catches_unexpected_exception(mock_config, tmp_path):
    with patch(
        "src.backend.coordinator.MustangRunner.check_installation",
        return_value=(True, "ok"),
    ), patch(
        "src.backend.coordinator.PDBManager.batch_download",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ):
        coordinator = AnalysisCoordinator(mock_config)
        success, msg, results = coordinator.run_full_pipeline(
            ["4RLT"], output_dir=tmp_path / "out"
        )

        assert success is False
        assert "boom" in msg
        assert results is None


class TestRunMustangAlignment:
    def test_clears_a_pre_existing_output_dir_before_realigning(
        self, mock_config, tmp_path
    ):
        """A stale output_dir from a previous run at the same path must be
        wiped before Mustang writes fresh output there, not merged with
        leftover files from the earlier run."""
        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ):
            coordinator = AnalysisCoordinator(mock_config)
            output_dir = tmp_path / "out"
            output_dir.mkdir()
            stale_file = output_dir / "stale.txt"
            stale_file.write_text("leftover from a previous run")

            with patch.object(
                coordinator.mustang_runner,
                "run_alignment",
                return_value=(True, "ok", output_dir),
            ):
                coordinator._run_mustang_alignment([], output_dir)

            assert not stale_file.exists()


class TestResolveRunIdentity:
    def test_uses_provided_output_dir_as_run_id(self, mock_config, tmp_path):
        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ):
            coordinator = AnalysisCoordinator(mock_config)
            output_dir = tmp_path / "my_run"

            resolved_dir, run_id, run_name, now = coordinator._resolve_run_identity(
                output_dir, ["4RLT"]
            )

            assert resolved_dir == output_dir
            assert run_id == "my_run"
            assert "Custom Run" in run_name

    def test_generates_fresh_run_id_when_no_output_dir_given(self, mock_config):
        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ):
            coordinator = AnalysisCoordinator(mock_config, session_id="sess-1")

            resolved_dir, run_id, run_name, now = coordinator._resolve_run_identity(
                None, ["4RLT", "3UG9"]
            )

            assert run_id.startswith("run")
            assert "sess-1" in str(resolved_dir)
            assert "2 structures" in run_name


def _pocket_atom_line(serial, name, resname, chain, resi, x, y, z, hetatm=False):
    record = "HETATM" if hetatm else "ATOM  "
    name_field = f" {name:<3}"
    element = name.strip()[0]
    return (
        f"{record}{serial:>5} {name_field} {resname:>3} {chain}{resi:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{20.00:6.2f}"
        f"{'':>10}{element:>2}"
    )


class TestAnalyzeLigands:
    def test_pdb_with_a_ligand_reports_it_and_collects_its_interactions(
        self, mock_config, tmp_path
    ):
        pdb_file = tmp_path / "4hhb.pdb"
        pdb_file.write_text(
            "\n".join(
                [
                    _pocket_atom_line(1, "N", "ALA", "A", 1, 0.0, 1.0, 0.0),
                    _pocket_atom_line(2, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
                    _pocket_atom_line(3, "C1", "HEM", "A", 100, 0.5, 0.5, 0.5, True),
                    "TER",
                ]
            )
            + "\n"
        )

        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ):
            coordinator = AnalysisCoordinator(mock_config)

        ligand_analysis, all_interactions = coordinator._analyze_ligands([pdb_file])

        assert ligand_analysis["4HHB"][0]["name"] == "HEM"
        assert len(all_interactions) == 1
        # Namespaced with the structure ID so identically-named ligands
        # from different structures don't collide in the similarity matrix.
        assert all_interactions[0]["ligand"] == "4HHB:HEM_A_100"

    def test_pdb_with_no_ligands_reports_empty_list_and_no_interactions(
        self, mock_config, tmp_path
    ):
        pdb_file = tmp_path / "1crn.pdb"
        pdb_file.write_text(
            _pocket_atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0) + "\nTER\n"
        )

        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ):
            coordinator = AnalysisCoordinator(mock_config)

        ligand_analysis, all_interactions = coordinator._analyze_ligands([pdb_file])

        assert ligand_analysis == {"1CRN": []}
        assert all_interactions == []

    def test_ligand_with_zero_interactions_is_excluded(self, mock_config, tmp_path):
        """A ligand with no protein neighbors within the cutoff (e.g. it
        sits alone with nothing else in the file) can't contribute a
        pocket fingerprint - excluding it here means an "empty pocket"
        never masquerades as a real dissimilarity signal downstream."""
        pdb_file = tmp_path / "lonely.pdb"
        pdb_file.write_text(
            _pocket_atom_line(1, "C1", "LIG", "A", 100, 0.0, 0.0, 0.0, True) + "\nTER\n"
        )

        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ):
            coordinator = AnalysisCoordinator(mock_config)

        ligand_analysis, all_interactions = coordinator._analyze_ligands([pdb_file])

        assert len(ligand_analysis["LONELY"]) == 1
        assert all_interactions == []

    def test_get_ligands_failure_for_one_structure_does_not_abort_the_batch(
        self, mock_config, tmp_path
    ):
        """A crash detecting ligands in one structure (e.g. a corrupt file)
        must not prevent ligand analysis from completing for the rest."""
        bad_file = tmp_path / "bad.pdb"
        bad_file.write_text("garbage")
        good_file = tmp_path / "1crn.pdb"
        good_file.write_text(
            _pocket_atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0) + "\nTER\n"
        )

        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ):
            coordinator = AnalysisCoordinator(mock_config)

        with patch.object(
            coordinator.ligand_analyzer,
            "get_ligands",
            side_effect=[RuntimeError("corrupt file"), []],
        ):
            ligand_analysis, all_interactions = coordinator._analyze_ligands(
                [bad_file, good_file]
            )

        assert ligand_analysis == {"BAD": [], "1CRN": []}
        assert all_interactions == []


class TestAttachLigandAnalysis:
    def test_always_sets_ligand_analysis(self, mock_config, tmp_path):
        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ), patch.object(
            AnalysisCoordinator,
            "_analyze_ligands",
            return_value=({"4RLT": []}, []),
        ):
            coordinator = AnalysisCoordinator(mock_config)
            results = {}
            coordinator._attach_ligand_analysis([tmp_path / "4rlt.pdb"], results)

        assert results["ligand_analysis"] == {"4RLT": []}
        assert "ligand_pocket_similarity" not in results

    def test_sets_pocket_similarity_only_with_at_least_two_interactions(
        self, mock_config, tmp_path
    ):
        one_interaction = [{"ligand": "4RLT:HEM_A_1", "interactions": [{}]}]
        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ), patch.object(
            AnalysisCoordinator,
            "_analyze_ligands",
            return_value=({"4RLT": [{"name": "HEM"}]}, one_interaction),
        ):
            coordinator = AnalysisCoordinator(mock_config)
            results = {}
            coordinator._attach_ligand_analysis([tmp_path / "4rlt.pdb"], results)

        assert "ligand_pocket_similarity" not in results

    def test_computes_pocket_similarity_with_two_or_more_interactions(
        self, mock_config, tmp_path
    ):
        two_interactions = [
            {"ligand": "4HHB:HEM_A_1", "interactions": [{"residue": "HIS"}]},
            {"ligand": "2HHB:HEM_A_1", "interactions": [{"residue": "HIS"}]},
        ]
        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ), patch.object(
            AnalysisCoordinator,
            "_analyze_ligands",
            return_value=({}, two_interactions),
        ):
            coordinator = AnalysisCoordinator(mock_config)
            results = {}
            coordinator._attach_ligand_analysis([tmp_path / "x.pdb"], results)

        sim_df = results["ligand_pocket_similarity"]
        assert sim_df.loc["4HHB:HEM_A_1", "2HHB:HEM_A_1"] == 1.0

    def test_swallows_exceptions_and_leaves_a_safe_default(self, mock_config, tmp_path):
        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ), patch.object(
            AnalysisCoordinator,
            "_analyze_ligands",
            side_effect=RuntimeError("boom"),
        ):
            coordinator = AnalysisCoordinator(mock_config)
            results = {"some_other_key": "unchanged"}
            coordinator._attach_ligand_analysis([tmp_path / "x.pdb"], results)

        assert results["ligand_analysis"] == {}
        assert results["some_other_key"] == "unchanged"


class TestGenerateInsights:
    def test_populates_insights_on_success(self, mock_config):
        results = {"rmsd_df": None}
        with patch(
            "src.backend.insights.InsightsGenerator.generate_insights",
            return_value=["Some insight"],
        ):
            AnalysisCoordinator._generate_insights(mock_config, results)
        assert results["insights"] == ["Some insight"]

    def test_falls_back_to_empty_list_on_failure(self, mock_config):
        results = {"rmsd_df": None}
        with patch(
            "src.backend.insights.InsightsGenerator.generate_insights",
            side_effect=RuntimeError("boom"),
        ):
            AnalysisCoordinator._generate_insights(mock_config, results)
        assert results["insights"] == []


def test_run_full_pipeline_fails_when_download_fails(mock_config, tmp_path):
    with patch(
        "src.backend.coordinator.MustangRunner.check_installation",
        return_value=(True, "ok"),
    ), patch(
        "src.backend.coordinator.PDBManager.batch_download", new_callable=AsyncMock
    ) as mock_download:
        mock_download.return_value = {
            "9ZZZ": (False, "404 Not Found", None),
        }

        coordinator = AnalysisCoordinator(mock_config)
        success, msg, results = coordinator.run_full_pipeline(
            ["9ZZZ"], output_dir=tmp_path / "out"
        )

        assert success is False
        assert "9ZZZ" in msg
        assert results is None


class TestProcessResultDirectory:
    def test_real_two_structure_directory_produces_a_full_results_dict(
        self, mock_config, tmp_path
    ):
        """Runs the actual RMSD/heatmap/phylo/sequence pipeline against a
        real (if minimal) Mustang-shaped output directory - no mocking of
        the processing itself, only the constructor's installation check
        (no real Mustang binary needed to just process existing output)."""
        result_dir = tmp_path / "out"
        _write_alignment_fixture(result_dir)

        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ):
            coordinator = AnalysisCoordinator(mock_config)
            results = coordinator.process_result_directory(result_dir, ["4RLT", "3UG9"])

        assert results is not None
        assert results["pdb_ids"] == ["4RLT", "3UG9"]
        assert results["rmsd_df"].loc["4RLT", "3UG9"] == 1.5
        assert results["heatmap_path"].exists()
        assert results["stats"]["mean_rmsd"] == 1.5
        assert results["sequences"] is not None
        assert results["stats"]["seq_identity"] == 100.0
        assert results["tree_path"].exists()
        assert results["newick_path"].exists()
        assert results["heatmap_fig"] is not None
        assert results["tree_fig"] is not None

    def test_returns_none_when_no_rmsd_data_can_be_parsed(self, mock_config, tmp_path):
        result_dir = tmp_path / "out"
        result_dir.mkdir()
        # No .rms_rot, no mustang.log, no alignment.pdb/.afasta pair -
        # every parse_rmsd_matrix() strategy fails.

        with patch(
            "src.backend.coordinator.MustangRunner.check_installation",
            return_value=(True, "ok"),
        ):
            coordinator = AnalysisCoordinator(mock_config)
            results = coordinator.process_result_directory(result_dir, ["4RLT", "3UG9"])

        assert results is None


def test_run_full_pipeline_succeeds_end_to_end(mock_config, tmp_path):
    """Full happy path through run_full_pipeline() - PDB download/cleaning/
    Mustang are mocked (no real network or Mustang binary needed), but
    process_result_directory, history persistence, and metadata.json
    writing all run for real against a real alignment output directory."""
    progress_calls = []

    with patch(
        "src.backend.coordinator.MustangRunner.check_installation",
        return_value=(True, "ok"),
    ), patch(
        "src.backend.coordinator.PDBManager.batch_download", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.backend.coordinator.PDBManager.analyze_structure"
    ) as mock_analyze, patch(
        "src.backend.coordinator.PDBManager.clean_pdb"
    ) as mock_clean, patch(
        "src.backend.coordinator.MustangRunner.run_alignment"
    ) as mock_align, patch(
        "src.backend.coordinator.HistoryDatabase.save_run", return_value=True
    ) as mock_save_run:
        raw_4rlt = tmp_path / "4rlt.pdb"
        raw_3ug9 = tmp_path / "3ug9.pdb"
        raw_4rlt.write_text("ATOM")
        raw_3ug9.write_text("ATOM")
        mock_download.return_value = {
            "4RLT": (True, "ok", raw_4rlt),
            "3UG9": (True, "ok", raw_3ug9),
        }
        mock_analyze.return_value = {"chains": [{"id": "A", "residue_count": 100}]}

        def fake_clean_pdb(pdb_file, **kw):
            cleaned_path = tmp_path / f"cleaned_{pdb_file.name}"
            cleaned_path.write_text("ATOM")
            return True, "ok", cleaned_path

        mock_clean.side_effect = fake_clean_pdb

        output_dir = tmp_path / "run_out"

        def fake_run_alignment(cleaned_files, out_dir):
            # Mustang's real behavior: populate out_dir with alignment
            # output. We write the same realistic fixture used to test
            # process_result_directory directly.
            _write_alignment_fixture(out_dir)
            return True, "ok", out_dir

        mock_align.side_effect = fake_run_alignment

        coordinator = AnalysisCoordinator(mock_config)
        success, msg, results = coordinator.run_full_pipeline(
            ["4RLT", "3UG9"],
            output_dir=output_dir,
            progress_callback=lambda frac, text, step: progress_calls.append(
                (frac, step)
            ),
        )

    assert success is True
    assert results is not None
    assert results["id"] == output_dir.name
    assert results["stats"]["mean_rmsd"] == 1.5
    assert (output_dir / "metadata.json").exists()
    # Ligand-free/garbage-content input still succeeds and produces the
    # expected empty-but-present shape, not a missing key or a failure.
    assert results["ligand_analysis"] == {"4RLT": [], "3UG9": []}
    # All 4 pipeline stages reported progress, ending at 100%.
    assert progress_calls[0] == (0.1, 1)
    assert progress_calls[-1] == (1.0, 4)
    mock_save_run.assert_called_once()
