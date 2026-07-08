import shutil

from streamlit.testing.v1 import AppTest


def _atom_line(serial, name, resname, chain, resi, x, y, z, hetatm=False):
    record = "HETATM" if hetatm else "ATOM  "
    name_field = f" {name:<3}"
    element = name.strip()[0]
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
        _atom_line(8, "C1", "LIG", "A", 100, 0.5, 0.5, 0.5, hetatm=True),
        _atom_line(9, "C2", "LIG", "A", 100, 1.0, 1.0, 1.0, hetatm=True),
        "TER",
    ]
    return "\n".join(lines) + "\n"


def _run(script, tmp_path, monkeypatch):
    shutil.copy("config.yaml", tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_string(script)
    at.run(timeout=60)
    return at


INIT = """
import streamlit as st
from src.utils.session_manager import SessionInitializer
SessionInitializer.initialize()
"""


class TestRenderLigandTab:
    def test_finds_real_ligand_in_single_tab(self, tmp_path, monkeypatch):
        raw_dir = tmp_path / "data" / "raw"
        raw_dir.mkdir(parents=True)
        (raw_dir / "TEST.pdb").write_text(_fixture_pdb_text())
        result_dir = tmp_path / "results" / "run_1"
        result_dir.mkdir(parents=True)

        script = (
            INIT
            + 'st.session_state.pdb_ids = ["TEST"]\n'
            + "from src.frontend.tabs.ligand import render_ligand_tab\n"
            + f'render_ligand_tab({{"result_dir": __import__("pathlib").Path(r"{result_dir}")}})\n'
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("Found 1 ligands" in s.value for s in at.success)

    def test_missing_pdb_file_shows_error(self, tmp_path, monkeypatch):
        result_dir = tmp_path / "results" / "run_1"
        result_dir.mkdir(parents=True)
        script = (
            INIT
            + 'st.session_state.pdb_ids = ["NOPE"]\n'
            + "from src.frontend.tabs.ligand import render_ligand_tab\n"
            + f'render_ligand_tab({{"result_dir": __import__("pathlib").Path(r"{result_dir}")}})\n'
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("PDB file not found" in e.value for e in at.error)

    def test_pocket_comparison_tab_warns_with_insufficient_history(
        self, tmp_path, monkeypatch
    ):
        result_dir = tmp_path / "results" / "run_1"
        result_dir.mkdir(parents=True)
        script = (
            INIT
            + 'st.session_state.pdb_ids = ["NOPE"]\n'
            + "from src.frontend.tabs.ligand import render_ligand_tab\n"
            + f'render_ligand_tab({{"result_dir": __import__("pathlib").Path(r"{result_dir}")}})\n'
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("Analyze at least 2" in w.value for w in at.warning)
