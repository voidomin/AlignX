from unittest.mock import Mock, patch

import httpx
import pandas as pd
import pytest

from src.backend.ligand_analyzer import LigandAnalyzer
from tests.conftest import MINIMAL_CIF_HEADER


def _atom_line(serial, name, resname, chain, resi, x, y, z, hetatm=False, element=None):
    record = "HETATM" if hetatm else "ATOM  "
    name_field = f" {name:<3}"
    # Only correct for single-letter elements (fine for every existing
    # fixture, which are all C/N/O) - a two-letter element (e.g. Zn) must
    # pass its real symbol explicitly, since name[0] alone would be wrong.
    element = element or name.strip()[0]
    return (
        f"{record}{serial:>5} {name_field} {resname:>3} {chain}{resi:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{20.00:6.2f}"
        f"{'':>10}{element:>2}"
    )


def _fixture_pdb_text():
    lines = [
        _atom_line(1, "N", "ALA", "A", 1, 0.0, 1.0, 0.0),
        _atom_line(2, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom_line(3, "C", "ALA", "A", 1, 1.0, 0.0, 0.0),
        _atom_line(4, "O", "ALA", "A", 1, 1.5, -1.0, 0.0),
        _atom_line(5, "CB", "ALA", "A", 1, -1.0, -1.0, 0.0),
        _atom_line(6, "N", "GLY", "A", 2, 50.0, 0.0, 0.0),
        _atom_line(7, "CA", "GLY", "A", 2, 51.0, 0.0, 0.0),
        _atom_line(8, "C1", "LIG", "A", 100, 0.5, 0.5, 0.5, hetatm=True),
        _atom_line(9, "C2", "LIG", "A", 100, 1.0, 1.0, 1.0, hetatm=True),
        _atom_line(10, "O", "HOH", "A", 200, 100.0, 100.0, 100.0, hetatm=True),
        "TER",
    ]
    return "\n".join(lines) + "\n"


@pytest.fixture
def fixture_pdb(tmp_path):
    pdb_file = tmp_path / "fixture.pdb"
    pdb_file.write_text(_fixture_pdb_text())
    return pdb_file


def _minimal_cif_text():
    # Same minimal atom_site loop shape as a real AlphaFold-sourced download
    # (see tests/conftest.py's MINIMAL_CIF_HEADER) - group_PDB HETATM for
    # the ZN row, so this also exercises get_ligands() finding a real
    # metal-cofactor ligand through the mmCIF parsing path, not just PDB.
    return MINIMAL_CIF_HEADER + (
        "ATOM 1 N N . ALA A 1 1 ? 11.104 13.203 7.334 1.00 20.00 ? 1 A 1\n"
        "ATOM 2 C CA . ALA A 1 1 ? 12.104 14.203 8.334 1.00 20.00 ? 1 A 1\n"
        "HETATM 3 ZN ZN . ZN A 2 . ? 13.604 14.703 8.834 1.00 20.00 ? 100 A 1\n"
    )


class TestGetLigands:
    def test_finds_ligand_and_ignores_water(self, fixture_pdb):
        analyzer = LigandAnalyzer()

        ligands = analyzer.get_ligands(fixture_pdb)

        assert len(ligands) == 1
        assert ligands[0]["name"] == "LIG"
        assert ligands[0]["id"] == "LIG_A_100"
        assert ligands[0]["chain"] == "A"
        assert ligands[0]["resi"] == 100
        assert ligands[0]["atom_count"] == 2
        assert ligands[0]["center"] == pytest.approx([0.75, 0.75, 0.75])

    def test_returns_empty_list_for_missing_file(self, tmp_path):
        analyzer = LigandAnalyzer()
        assert analyzer.get_ligands(tmp_path / "nope.pdb") == []

    def test_returns_empty_list_on_parse_failure(self, tmp_path):
        analyzer = LigandAnalyzer()
        assert analyzer.get_ligands(tmp_path) == []

    def test_recognizes_a_catalytic_zinc_ion_as_a_real_ligand(self, tmp_path):
        # v3.87.0: metal cofactors (ZN/MG/CA/MN/FE/etc.) used to be lumped
        # into ignored_residues alongside water/buffer junk - a catalytic
        # zinc should now come back as a real ligand, same as any other
        # HETATM, not be silently dropped.
        lines = [
            _atom_line(1, "N", "HIS", "A", 1, 0.0, 1.0, 0.0),
            _atom_line(2, "CA", "HIS", "A", 1, 0.0, 0.0, 0.0),
            _atom_line(3, "ND1", "HIS", "A", 1, 2.0, 0.0, 0.0),
            _atom_line(
                4, "ZN", "ZN", "A", 100, 3.0, 0.0, 0.0, hetatm=True, element="ZN"
            ),
            "TER",
        ]
        pdb_file = tmp_path / "zinc.pdb"
        pdb_file.write_text("\n".join(lines) + "\n")
        analyzer = LigandAnalyzer()

        ligands = analyzer.get_ligands(pdb_file)

        assert len(ligands) == 1
        assert ligands[0]["name"] == "ZN"
        assert ligands[0]["id"] == "ZN_A_100"

    def test_non_catalytic_ions_and_buffer_components_still_ignored(self, tmp_path):
        lines = [
            _atom_line(1, "N", "ALA", "A", 1, 0.0, 1.0, 0.0),
            _atom_line(2, "NA", "NA", "A", 100, 5.0, 5.0, 5.0, hetatm=True),
            _atom_line(3, "S", "SO4", "A", 101, 6.0, 6.0, 6.0, hetatm=True),
            "TER",
        ]
        pdb_file = tmp_path / "buffer.pdb"
        pdb_file.write_text("\n".join(lines) + "\n")
        analyzer = LigandAnalyzer()

        assert analyzer.get_ligands(pdb_file) == []

    def test_parses_a_real_cif_file_without_crashing(self, tmp_path):
        # Regression: every parsing method here used to hardcode
        # Bio.PDB.PDBParser regardless of file extension, which throws
        # KeyError: 0 on structure[0] for a real AlphaFold-sourced .cif
        # file (PDBParser can't parse mmCIF syntax, so it silently builds
        # zero models) - this broke ligand analysis for every AlphaFold
        # structure, only caught by live end-to-end testing since no test
        # fixture anywhere used a real .cif file before this.
        cif_file = tmp_path / "af-test-f1.cif"
        cif_file.write_text(_minimal_cif_text())
        analyzer = LigandAnalyzer()

        ligands = analyzer.get_ligands(cif_file)

        assert len(ligands) == 1
        assert ligands[0]["name"] == "ZN"


class TestCalculateInteractions:
    def test_finds_nearby_residue_and_excludes_far_one(self, fixture_pdb):
        analyzer = LigandAnalyzer()

        result = analyzer.calculate_interactions(fixture_pdb, "LIG_A_100", cutoff=5.0)

        assert result["ligand"] == "LIG_A_100"
        residues = {i["residue"] for i in result["interactions"]}
        assert residues == {"ALA"}
        entry = result["interactions"][0]
        assert entry["type"] == "Van der Waals"
        assert entry["distance"] < 5.0
        assert result["pocket_sasa"] >= 0

    def test_invalid_ligand_id_format_reports_error(self, fixture_pdb):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_interactions(fixture_pdb, "badformat")
        assert result == {"error": "Invalid ID"}

    def test_ligand_not_found_reports_error(self, fixture_pdb):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_interactions(fixture_pdb, "XXX_A_999")
        assert "not found" in result["error"]

    def test_parse_failure_reports_error(self, tmp_path):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_interactions(tmp_path, "LIG_A_100")
        assert "error" in result

    def test_zinc_ion_interactions_classified_as_metal_coordination(self, tmp_path):
        # End-to-end (not just classify_contact in isolation): a His ND1
        # 2.0 A from a real Zn ligand should come back through the full
        # calculate_interactions() pipeline as "Metal Coordination".
        lines = [
            _atom_line(1, "N", "HIS", "A", 1, 0.0, 1.0, 0.0),
            _atom_line(2, "CA", "HIS", "A", 1, 0.0, 0.0, 0.0),
            _atom_line(3, "ND1", "HIS", "A", 1, 2.0, 0.0, 0.0),
            _atom_line(
                4, "ZN", "ZN", "A", 100, 4.0, 0.0, 0.0, hetatm=True, element="ZN"
            ),
            "TER",
        ]
        pdb_file = tmp_path / "zinc.pdb"
        pdb_file.write_text("\n".join(lines) + "\n")
        analyzer = LigandAnalyzer()

        result = analyzer.calculate_interactions(pdb_file, "ZN_A_100", cutoff=5.0)

        assert result["ligand"] == "ZN_A_100"
        entry = next(i for i in result["interactions"] if i["residue"] == "HIS")
        assert entry["type"] == "Metal Coordination"


class TestCalculateSasa:
    def test_returns_total_chain_and_residue_breakdown(self, fixture_pdb):
        analyzer = LigandAnalyzer()

        result = analyzer.calculate_sasa(fixture_pdb)

        assert result["total_sasa"] >= 0
        assert "A" in result["chain_sasa"]
        residue_names = {r["residue"] for r in result["residues"]}
        assert residue_names == {"ALA", "GLY"}

    def test_returns_error_on_parse_failure(self, tmp_path):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_sasa(tmp_path)
        assert "error" in result


def _residue_lines(start_serial, resname, chain, resi, center):
    """A minimal backbone+CB residue (enough atoms for BioPython's
    ShrakeRupley to compute a real, non-zero SASA) placed around a given
    center coordinate."""
    x, y, z = center
    return [
        _atom_line(start_serial, "N", resname, chain, resi, x, y + 1.0, z),
        _atom_line(start_serial + 1, "CA", resname, chain, resi, x, y, z),
        _atom_line(start_serial + 2, "C", resname, chain, resi, x + 1.0, y, z),
        _atom_line(start_serial + 3, "O", resname, chain, resi, x + 1.5, y - 1.0, z),
        _atom_line(start_serial + 4, "CB", resname, chain, resi, x - 1.0, y - 1.0, z),
    ]


class TestFindCandidatePockets:
    def test_finds_a_spatial_cluster_of_sequence_distant_surface_residues(
        self, tmp_path
    ):
        # 4 residues far apart in sequence (1, 50, 100, 150 - all > the 5-
        # residue sequence-gap threshold from one another) but placed
        # within a few Angstroms of each other in 3D and otherwise
        # isolated (so they're fully solvent-exposed, real non-zero SASA)
        # - exactly the "fold packs together from distant sequence
        # regions" signature this heuristic looks for.
        lines = []
        lines += _residue_lines(1, "LEU", "A", 1, (0.0, 0.0, 0.0))
        lines += _residue_lines(6, "PHE", "A", 50, (4.0, 0.0, 0.0))
        lines += _residue_lines(11, "TRP", "A", 100, (0.0, 4.0, 0.0))
        lines += _residue_lines(16, "TYR", "A", 150, (0.0, 0.0, 4.0))
        lines.append("TER")
        pdb_file = tmp_path / "pocket.pdb"
        pdb_file.write_text("\n".join(lines) + "\n")
        analyzer = LigandAnalyzer()

        pockets = analyzer.find_candidate_pockets(pdb_file)

        assert len(pockets) >= 1
        top = pockets[0]
        assert top["rank"] == 1
        assert top["heuristic"] is True
        assert len(top["residues"]) >= 4
        found_resi = {r["resi"] for r in top["residues"]}
        assert found_resi.issubset({1, 50, 100, 150})
        assert len(top["center"]) == 3
        # The 4 cluster centers form a real tetrahedron (non-coplanar), so
        # a convex hull volume should compute to a real positive value.
        assert top["volume_estimate_a3"] is not None
        assert top["volume_estimate_a3"] > 0

    def test_volume_estimate_is_none_for_a_coplanar_cluster(self, tmp_path):
        # All 4 residue centers share z=0 - scipy's ConvexHull can't
        # construct a 3D hull from coplanar points, so this must degrade
        # to None rather than raising.
        lines = []
        lines += _residue_lines(1, "LEU", "A", 1, (0.0, 0.0, 0.0))
        lines += _residue_lines(6, "PHE", "A", 50, (4.0, 0.0, 0.0))
        lines += _residue_lines(11, "TRP", "A", 100, (0.0, 4.0, 0.0))
        lines += _residue_lines(16, "TYR", "A", 150, (4.0, 4.0, 0.0))
        lines.append("TER")
        pdb_file = tmp_path / "coplanar_pocket.pdb"
        pdb_file.write_text("\n".join(lines) + "\n")
        analyzer = LigandAnalyzer()

        pockets = analyzer.find_candidate_pockets(pdb_file)

        assert len(pockets) >= 1
        assert pockets[0]["volume_estimate_a3"] is None

    def test_no_surface_residues_returns_empty_list(self, fixture_pdb):
        # fixture_pdb's ALA/GLY pair is too small/isolated a residue set to
        # register a real cluster (needs MIN_CLUSTER_NEIGHBORS=3 distant
        # neighbors within range, which 2 residues total can never reach).
        analyzer = LigandAnalyzer()
        assert analyzer.find_candidate_pockets(fixture_pdb) == []

    def test_returns_empty_list_on_parse_failure(self, tmp_path):
        analyzer = LigandAnalyzer()
        assert analyzer.find_candidate_pockets(tmp_path) == []

    def test_selected_pockets_never_share_a_residue(self, tmp_path):
        # Two well-separated 4-residue clusters (>20 A apart) should come
        # back as two distinct, non-overlapping candidates - the greedy
        # dedup-by-residue step should never let the same residue appear
        # in two returned pockets.
        lines = []
        lines += _residue_lines(1, "LEU", "A", 1, (0.0, 0.0, 0.0))
        lines += _residue_lines(6, "PHE", "A", 50, (4.0, 0.0, 0.0))
        lines += _residue_lines(11, "TRP", "A", 100, (0.0, 4.0, 0.0))
        lines += _residue_lines(16, "TYR", "A", 150, (0.0, 0.0, 4.0))
        lines += _residue_lines(21, "MET", "A", 200, (50.0, 50.0, 50.0))
        lines += _residue_lines(26, "ILE", "A", 250, (54.0, 50.0, 50.0))
        lines += _residue_lines(31, "VAL", "A", 300, (50.0, 54.0, 50.0))
        lines += _residue_lines(36, "CYS", "A", 350, (50.0, 50.0, 54.0))
        lines.append("TER")
        pdb_file = tmp_path / "two_pockets.pdb"
        pdb_file.write_text("\n".join(lines) + "\n")
        analyzer = LigandAnalyzer()

        pockets = analyzer.find_candidate_pockets(pdb_file, top_n=5)

        all_residue_keys = [
            (p["rank"], r["resi"]) for p in pockets for r in p["residues"]
        ]
        seen = set()
        for rank, resi in all_residue_keys:
            key = resi
            assert key not in seen, "a residue appeared in more than one pocket"
            seen.add(key)


class TestCalculateInteractionSimilarity:
    def test_empty_input_returns_empty_dataframe(self):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_interaction_similarity([])
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_diagonal_is_one_and_off_diagonal_is_jaccard(self):
        analyzer = LigandAnalyzer()
        all_interactions = [
            {
                "ligand": "L1",
                "interactions": [{"residue": "ALA"}, {"residue": "GLY"}],
            },
            {
                "ligand": "L2",
                "interactions": [{"residue": "ALA"}, {"residue": "SER"}],
            },
        ]

        result = analyzer.calculate_interaction_similarity(all_interactions)

        assert result.loc["L1", "L1"] == 1.0
        assert result.loc["L2", "L2"] == 1.0
        assert result.loc["L1", "L2"] == pytest.approx(1 / 3)

    def test_empty_fingerprint_scores_zero_not_undefined(self):
        analyzer = LigandAnalyzer()
        all_interactions = [
            {"ligand": "L1", "interactions": [{"residue": "ALA"}]},
            {"ligand": "L2", "interactions": []},
        ]

        result = analyzer.calculate_interaction_similarity(all_interactions)

        assert result.loc["L1", "L2"] == 0.0


class TestJaccardScore:
    def test_both_empty_scores_zero(self):
        assert LigandAnalyzer._jaccard_score(set(), set()) == 0.0

    def test_identical_sets_score_one(self):
        assert LigandAnalyzer._jaccard_score({"A", "B"}, {"A", "B"}) == 1.0

    def test_disjoint_sets_score_zero(self):
        assert LigandAnalyzer._jaccard_score({"A"}, {"B"}) == 0.0


def _mock_response(status_code=200, json_data=None):
    mock = Mock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    return mock


class TestFetchLigandChemistry:
    @pytest.mark.asyncio
    @patch("src.backend.ligand_analyzer.httpx.AsyncClient.get")
    async def test_parses_name_formula_and_smiles(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={
                "chem_comp": {
                    "name": "PROTOPORPHYRIN IX CONTAINING FE",
                    "formula": "C34 H32 Fe N4 O4",
                    "formula_weight": 616.487,
                },
                "rcsb_chem_comp_descriptor": {
                    "SMILES": "CC1=C(C=C)C2=CC3=C(C)C(CCC(O)=O)=C4C=C5C(CCC(O)=O)=C(C)C6=CC7=C(C)C(C=C)=C8C=C1[N-]2[Fe+2]([N-]34)([N-]56)N78",
                    "InChIKey": "KABFMIBPWCXCRK-RGGAHWMASA-L",
                },
            }
        )
        analyzer = LigandAnalyzer()
        async with httpx.AsyncClient() as client:
            result = await analyzer.fetch_ligand_chemistry("HEM", client)

        assert result["id"] == "HEM"
        assert result["name"] == "PROTOPORPHYRIN IX CONTAINING FE"
        assert result["formula"] == "C34 H32 Fe N4 O4"
        assert result["formula_weight"] == 616.487
        assert result["smiles"].startswith("CC1=C")
        assert result["inchi_key"] == "KABFMIBPWCXCRK-RGGAHWMASA-L"

    @pytest.mark.asyncio
    @patch("src.backend.ligand_analyzer.httpx.AsyncClient.get")
    async def test_lowercases_input_before_the_request(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={"chem_comp": {"name": "HEME", "formula": "C34 H32 Fe N4 O4"}}
        )
        analyzer = LigandAnalyzer()
        async with httpx.AsyncClient() as client:
            result = await analyzer.fetch_ligand_chemistry("hem", client)

        assert result["id"] == "HEM"
        assert mock_get.call_args.args[0].endswith("/HEM")

    @pytest.mark.asyncio
    @patch("src.backend.ligand_analyzer.httpx.AsyncClient.get")
    async def test_returns_none_when_no_name_or_formula_present(self, mock_get):
        mock_get.return_value = _mock_response(json_data={"chem_comp": {}})
        analyzer = LigandAnalyzer()
        async with httpx.AsyncClient() as client:
            result = await analyzer.fetch_ligand_chemistry("XXX", client)
        assert result is None

    @pytest.mark.asyncio
    @patch("src.backend.ligand_analyzer.httpx.AsyncClient.get")
    async def test_returns_none_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(status_code=404)
        analyzer = LigandAnalyzer()
        async with httpx.AsyncClient() as client:
            result = await analyzer.fetch_ligand_chemistry("ZZZ", client)
        assert result is None

    @pytest.mark.asyncio
    @patch("src.backend.ligand_analyzer.httpx.AsyncClient.get")
    async def test_returns_none_on_http_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        analyzer = LigandAnalyzer()
        async with httpx.AsyncClient() as client:
            result = await analyzer.fetch_ligand_chemistry("HEM", client)
        assert result is None

    @pytest.mark.asyncio
    @patch("src.backend.ligand_analyzer.httpx.AsyncClient.get")
    async def test_rejects_an_unsafe_ligand_code_without_making_a_request(
        self, mock_get
    ):
        analyzer = LigandAnalyzer()
        async with httpx.AsyncClient() as client:
            result = await analyzer.fetch_ligand_chemistry("../etc/passwd", client)
        assert result is None
        mock_get.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.backend.ligand_analyzer.httpx.AsyncClient.get")
    async def test_uses_cache_on_second_call_not_network(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={"chem_comp": {"name": "HEME", "formula": "C34 H32 Fe N4 O4"}}
        )
        cache_store = {}

        class FakeCacheDb:
            def get_annotation_cache(self, key, max_age_days):
                return cache_store.get(key)

            def set_annotation_cache(self, key, service, payload):
                cache_store[key] = payload

        analyzer = LigandAnalyzer(cache_db=FakeCacheDb())
        async with httpx.AsyncClient() as client:
            first = await analyzer.fetch_ligand_chemistry("HEM", client)
            second = await analyzer.fetch_ligand_chemistry("HEM", client)

        assert first == second
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.backend.ligand_analyzer.httpx.AsyncClient.get")
    async def test_cache_read_failure_falls_back_to_network(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={"chem_comp": {"name": "HEME", "formula": "C34 H32 Fe N4 O4"}}
        )

        class BrokenCacheDb:
            def get_annotation_cache(self, key, max_age_days):
                raise RuntimeError("cache down")

            def set_annotation_cache(self, key, service, payload):
                raise RuntimeError("cache down")

        analyzer = LigandAnalyzer(cache_db=BrokenCacheDb())
        async with httpx.AsyncClient() as client:
            result = await analyzer.fetch_ligand_chemistry("HEM", client)

        assert result["name"] == "HEME"

    def test_partial_overlap(self):
        assert LigandAnalyzer._jaccard_score({"A", "B"}, {"A", "C"}) == pytest.approx(
            1 / 3
        )
