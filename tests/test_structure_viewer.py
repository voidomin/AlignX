from src.backend.structure_viewer import (
    render_3d_structure,
    render_synced_grid,
    render_ligand_view,
)


def test_render_3d_structure(tmp_path, dummy_pdb_content):
    """Test 3D structure HTML generation."""
    pdb_file = tmp_path / "test.pdb"
    pdb_file.write_text(dummy_pdb_content)

    # Test basic render
    html = render_3d_structure(pdb_file, unique_id="test_1")
    assert html is not None
    assert "$3Dmol.createViewer" in html
    assert "container_test_1" in html
    assert dummy_pdb_content in html

    # Test with highlight
    html_hl = render_3d_structure(
        pdb_file, unique_id="test_hl", highlight_residues={"A": [1, 2]}
    )
    assert html_hl is not None
    assert '"A": [1, 2]' in html_hl


def test_render_3d_structure_auto_rotation_stops_itself(tmp_path, dummy_pdb_content):
    """viewer.spin() drives an unbounded requestAnimationFrame render loop
    with no built-in timeout - since this view can be one of 4 simultaneous
    viewers on screen at once (see _render_superimposed_view), that many
    perpetual spin loops is real, sustained GPU/CPU load, not a one-time
    render cost. Must stop on its own after a few seconds, and immediately
    on user interaction."""
    pdb_file = tmp_path / "test.pdb"
    pdb_file.write_text(dummy_pdb_content)

    html = render_3d_structure(pdb_file, unique_id="test_1")

    assert "setTimeout(() => viewer.spin(false), 3000)" in html
    assert 'addEventListener("mousedown"' in html
    assert 'addEventListener("touchstart"' in html
    assert 'addEventListener("wheel"' in html


def test_render_synced_grid(tmp_path, dummy_pdb_content):
    """Test synchronized 3D grid layout generation."""
    pdb_file = tmp_path / "aligned.pdb"
    pdb_file.write_text(dummy_pdb_content)

    members = ["protA", "protB"]
    html = render_synced_grid(pdb_file, members=members, height=200)

    assert html is not None
    assert "grid-container" in html
    assert "viewer_0" in html
    assert "viewer_1" in html
    assert "syncCameras" in html
    assert "protA (Chain A)" in html
    assert "protB (Chain B)" in html
    assert dummy_pdb_content in html


def test_render_ligand_view(tmp_path, dummy_pdb_content):
    """Test ligand pocket view generation."""
    pdb_file = tmp_path / "ligand_site.pdb"
    pdb_file.write_text(dummy_pdb_content)

    ligand_data = {
        "ligand": "RET_A_296",
        "interactions": [
            {
                "residue": "ALA",
                "chain": "A",
                "resi": 12,
                "distance": 3.4,
                "type": "Hydrophobic",
            },
            {
                "residue": "TYR",
                "chain": "A",
                "resi": 43,
                "distance": 2.8,
                "type": "H-Bond",
            },
        ],
    }

    # Test standard render
    html = render_ligand_view(pdb_file, ligand_data, unique_id="test_ligand")
    assert html is not None
    assert "ligand_test_ligand" in html
    assert "magentaCarbon" in html
    assert "chain: 'A'" in html
    assert "resi: 296" in html
    assert "resn: 'RET'" in html
    assert "activeResidues" in html
    assert dummy_pdb_content in html

    # Test with interactive highlighted rows
    html_hl = render_ligand_view(
        pdb_file, ligand_data, unique_id="test_ligand_hl", highlight_indices=[0]
    )
    assert html_hl is not None
    # Verify yellow stick formatting and sphere/label structures are output
    assert "yellowCarbon" in html_hl
    assert "highlightedResidues" in html_hl
    assert "addLabel" in html_hl
    assert 'sel.chain + ":" + sel.resi' in html_hl


def test_render_ligand_view_auto_rotation_stops_itself(tmp_path, dummy_pdb_content):
    """Same unbounded-spin-loop risk as render_3d_structure - must stop on
    its own, and immediately on interaction, when no rows are highlighted
    (the only case where this view auto-rotates at all)."""
    pdb_file = tmp_path / "ligand_site.pdb"
    pdb_file.write_text(dummy_pdb_content)
    ligand_data = {
        "ligand": "RET_A_296",
        "interactions": [
            {
                "residue": "ALA",
                "chain": "A",
                "resi": 12,
                "distance": 3.4,
                "type": "Hydrophobic",
            },
        ],
    }

    html = render_ligand_view(pdb_file, ligand_data, unique_id="test_ligand")

    assert "setTimeout(() => viewer.spin(false), 3000)" in html
    assert 'addEventListener("mousedown"' in html
    assert 'addEventListener("touchstart"' in html
    assert 'addEventListener("wheel"' in html
