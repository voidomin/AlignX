from pathlib import Path

from src.backend.clash_calculator import calculate_clash_score


def _atom_line(
    serial, name, resname, chain, resseq, x, y, z, element="C", hetatm=False
):
    """A spec-correct fixed-width PDB ATOM/HETATM line (columns exactly as
    the PDB format defines them - name 13-16, resName 18-20, chainID 22,
    resSeq 23-26, x/y/z 31-54, element 77-78) since this module's element
    lookup and residue/chain grouping depend on those columns landing
    correctly, unlike test_flexibility_calculator.py's looser CA-only
    helper."""
    record = "HETATM" if hetatm else "ATOM"
    line = list(" " * 80)
    line[0:6] = f"{record:<6}"
    line[6:11] = f"{serial:>5}"
    line[12:16] = f"{name:<4}"
    line[17:20] = f"{resname:<3}"
    line[21] = chain
    line[22:26] = f"{resseq:>4}"
    line[30:38] = f"{x:>8.3f}"
    line[38:46] = f"{y:>8.3f}"
    line[46:54] = f"{z:>8.3f}"
    line[54:60] = f"{1.00:>6.2f}"
    line[60:66] = f"{0.00:>6.2f}"
    line[76:78] = f"{element:>2}"
    return "".join(line)


def _write_pdb(path: Path, atom_specs):
    """atom_specs: list of dicts with keys name/resname/chain/resseq/x/y/z
    and optional element/hetatm."""
    lines = [
        _atom_line(
            i,
            spec["name"],
            spec["resname"],
            spec["chain"],
            spec["resseq"],
            spec["x"],
            spec["y"],
            spec["z"],
            element=spec.get("element", "C"),
            hetatm=spec.get("hetatm", False),
        )
        for i, spec in enumerate(atom_specs, start=1)
    ]
    lines.append("END")
    path.write_text("\n".join(lines))


class TestCalculateClashScore:
    def test_flags_two_atoms_closer_than_their_combined_vdw_radii(self, tmp_path):
        # Two carbons 2.0 A apart in unrelated, non-adjacent residues -
        # well inside the 1.70 + 1.70 - 0.4 = 3.0 A clash threshold.
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(
            pdb_file,
            [
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 1,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                },
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 10,
                    "x": 2.0,
                    "y": 0.0,
                    "z": 0.0,
                },
            ],
        )

        result = calculate_clash_score(pdb_file)

        assert result is not None
        assert result["clash_count"] == 1
        assert result["atom_count"] == 2
        pair = result["clashing_pairs"][0]
        assert pair["residue_a"] == 1 and pair["residue_b"] == 10
        assert pair["distance"] == 2.0

    def test_does_not_flag_adjacent_backbone_atoms_as_a_clash(self, tmp_path):
        # A real peptide bond's C-N distance (~1.33 A) between sequentially
        # adjacent residues - would trivially "clash" under a naive
        # distance check, but is real covalent geometry, not a steric
        # problem.
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(
            pdb_file,
            [
                {
                    "name": "C",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 1,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "element": "C",
                },
                {
                    "name": "N",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 2,
                    "x": 1.33,
                    "y": 0.0,
                    "z": 0.0,
                    "element": "N",
                },
            ],
        )

        result = calculate_clash_score(pdb_file)

        assert result["clash_count"] == 0

    def test_does_not_flag_two_atoms_in_the_same_residue(self, tmp_path):
        # CA-CB is a real bond (~1.5 A) within one residue - excluding
        # same-residue pairs outright is what keeps this from registering.
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(
            pdb_file,
            [
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 1,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                },
                {
                    "name": "CB",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 1,
                    "x": 1.5,
                    "y": 0.0,
                    "z": 0.0,
                },
            ],
        )

        result = calculate_clash_score(pdb_file)

        assert result["clash_count"] == 0

    def test_flags_a_clash_between_different_chains_even_at_the_same_residue_number(
        self, tmp_path
    ):
        # The same-chain sequential-adjacency exclusion must not suppress
        # a real inter-chain clash just because the residue numbers
        # happen to line up (a common real scenario for a symmetric
        # oligomer).
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(
            pdb_file,
            [
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 1,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                },
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "B",
                    "resseq": 1,
                    "x": 2.0,
                    "y": 0.0,
                    "z": 0.0,
                },
            ],
        )

        result = calculate_clash_score(pdb_file)

        assert result["clash_count"] == 1

    def test_ignores_hydrogens_entirely(self, tmp_path):
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(
            pdb_file,
            [
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 1,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "element": "C",
                },
                {
                    "name": "H",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 20,
                    "x": 0.1,
                    "y": 0.0,
                    "z": 0.0,
                    "element": "H",
                },
            ],
        )

        result = calculate_clash_score(pdb_file)

        assert result["atom_count"] == 1
        assert result["clash_count"] == 0

    def test_ignores_water_and_other_hetatm_residues(self, tmp_path):
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(
            pdb_file,
            [
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 1,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                },
                {
                    "name": "O",
                    "resname": "HOH",
                    "chain": "A",
                    "resseq": 50,
                    "x": 0.5,
                    "y": 0.0,
                    "z": 0.0,
                    "element": "O",
                    "hetatm": True,
                },
            ],
        )

        result = calculate_clash_score(pdb_file)

        assert result["atom_count"] == 1
        assert result["clash_count"] == 0

    def test_returns_none_on_parse_failure(self, tmp_path):
        result = calculate_clash_score(tmp_path / "does_not_exist.pdb")
        assert result is None

    def test_clashscore_is_clashes_per_1000_atoms(self, tmp_path):
        # 1 clashing pair among 4 heavy atoms -> 1 / 4 * 1000 = 250.0.
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(
            pdb_file,
            [
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 1,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                },
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 10,
                    "x": 2.0,
                    "y": 0.0,
                    "z": 0.0,
                },
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 20,
                    "x": 50.0,
                    "y": 0.0,
                    "z": 0.0,
                },
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 30,
                    "x": 100.0,
                    "y": 0.0,
                    "z": 0.0,
                },
            ],
        )

        result = calculate_clash_score(pdb_file)

        assert result["atom_count"] == 4
        assert result["clash_count"] == 1
        assert result["clashscore"] == 250.0

    def test_no_clashes_returns_a_zero_clashscore_not_none(self, tmp_path):
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(
            pdb_file,
            [
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 1,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                },
                {
                    "name": "CA",
                    "resname": "ALA",
                    "chain": "A",
                    "resseq": 10,
                    "x": 50.0,
                    "y": 0.0,
                    "z": 0.0,
                },
            ],
        )

        result = calculate_clash_score(pdb_file)

        assert result is not None
        assert result["clash_count"] == 0
        assert result["clashscore"] == 0.0
