from unittest.mock import patch, AsyncMock

from src.backend.coordinator import AnalysisCoordinator


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
