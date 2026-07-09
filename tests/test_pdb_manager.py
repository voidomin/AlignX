import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import pytest
from src.backend.pdb_manager import PDBManager


class TestPDBManager:

    @patch("src.backend.pdb_manager.Path.mkdir")
    def test_initialization(self, _, mock_config, temp_workspace):
        """Test if PDBManager initializes directories correctly."""
        # Patch the hardcoded paths in PDBManager __init__ to use temp_workspace
        manager = PDBManager(mock_config)
        assert manager.pdb_source == mock_config["pdb"]["source_url"]
        assert manager.timeout == 5

    @patch("src.backend.pdb_manager.Path.mkdir")
    def test_initialization_accepts_safe_session_id(self, _, mock_config):
        manager = PDBManager(mock_config, session_id="abc-123_XYZ")
        assert manager.session_id == "abc-123_XYZ"
        assert manager.raw_dir == Path("data/raw/abc-123_XYZ")

    @pytest.mark.parametrize(
        "bad_session_id",
        ["../../etc", "a/b", "a\\b", "..", "session id with spaces"],
    )
    def test_initialization_rejects_path_traversal_session_id(
        self, mock_config, bad_session_id
    ):
        """FastAPI's own endpoints already validate session_id (an
        attacker-controlled query param) before constructing a
        coordinator/PDBManager - this is a second, independent check so a
        future caller that skips that validation can't construct a path
        outside data/raw or data/cleaned."""
        with pytest.raises(ValueError, match="Invalid session_id"):
            PDBManager(mock_config, session_id=bad_session_id)

    def test_pdb_id_validation(self):
        """Test PDB ID validation logic."""
        assert PDBManager.validate_pdb_id("1A0J") is True
        assert (
            PDBManager.validate_pdb_id("4hhb") is True
        )  # Case insensitive in regex? Actually regex is stricter
        # The regex in code is r'^[0-9][A-Za-z0-9]{3}$'
        assert PDBManager.validate_pdb_id("1a0j") is True
        assert PDBManager.validate_pdb_id("invalid") is False
        assert PDBManager.validate_pdb_id("12345") is False
        assert PDBManager.validate_pdb_id("1A0") is False

    def test_pdb_id_validation_swissmodel_and_esmfold(self):
        """SM- (SWISS-MODEL, keyed by UniProt) and ESM- (ESM Atlas, keyed by
        MGYP accession) IDs must validate; malformed variants must not."""
        assert PDBManager.validate_pdb_id("SM-P69905") is True
        assert PDBManager.validate_pdb_id("sm-p69905") is True
        assert PDBManager.validate_pdb_id("SM-") is False
        assert PDBManager.validate_pdb_id("ESM-MGYP002537940442") is True
        assert PDBManager.validate_pdb_id("esm-mgyp002537940442") is True
        assert PDBManager.validate_pdb_id("ESM-P69905") is False  # not an MGYP id

    def test_detect_source(self):
        assert PDBManager.detect_source("4RLT") == "pdb"
        assert PDBManager.detect_source("AF-P69905-F1") == "alphafold"
        assert PDBManager.detect_source("SM-P69905") == "swissmodel"
        assert PDBManager.detect_source("ESM-MGYP002537940442") == "esmfold"
        assert PDBManager.detect_source("af-p69905-f1") == "alphafold"

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_download_pdb_success(self, mock_get, mock_config, temp_workspace):
        """Test successful PDB download."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "4"}
        mock_response.content = b"ATOM"
        mock_get.return_value = mock_response

        # Init manager
        manager = PDBManager(mock_config)
        # Override directories to use temp path
        manager.raw_dir = temp_workspace["raw"]

        success, _, path = await manager.download_pdb("1A0J")

        assert success is True
        assert path.exists()
        assert path.name == "1a0j.pdb"
        assert path.read_bytes() == b"ATOM"

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_download_swissmodel_success(
        self, mock_get, mock_config, temp_workspace
    ):
        """SWISS-MODEL downloads must hit the UniProt-keyed repository URL
        and save real PDB bytes directly (no .cif conversion, unlike AlphaFold)."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b"ATOM SWISSMODEL"
        mock_get.return_value = mock_response

        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, _, path = await manager.download_pdb("SM-P69905")

        assert success is True
        assert path.name == "sm-p69905.pdb"
        assert path.read_bytes() == b"ATOM SWISSMODEL"
        called_url = mock_get.call_args[0][0]
        assert (
            called_url == "https://swissmodel.expasy.org/repository/uniprot/P69905.pdb"
        )

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_download_esmfold_success(
        self, mock_get, mock_config, temp_workspace
    ):
        """ESM Atlas downloads must hit the MGYP-keyed fetchPredictedStructure
        URL and save real PDB bytes directly."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b"ATOM ESMFOLD"
        mock_get.return_value = mock_response

        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, _, path = await manager.download_pdb("ESM-MGYP002537940442")

        assert success is True
        assert path.name == "esm-mgyp002537940442.pdb"
        assert path.read_bytes() == b"ATOM ESMFOLD"
        called_url = mock_get.call_args[0][0]
        assert (
            called_url
            == "https://api.esmatlas.com/fetchPredictedStructure/MGYP002537940442"
        )

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_download_swissmodel_not_found(
        self, mock_get, mock_config, temp_workspace
    ):
        """A 404 from SWISS-MODEL must be reported as a clean failure, not a crash."""
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, msg, path = await manager.download_pdb("SM-NOTREAL")

        assert success is False
        assert path is None
        assert "SWISS-MODEL" in msg

    def test_analyze_structure(self, mock_config, temp_workspace, dummy_pdb_content):
        """Test structure analysis (chain counting)."""
        manager = PDBManager(mock_config)

        # Create dummy file
        p = temp_workspace["raw"] / "test.pdb"
        p.write_text(dummy_pdb_content)

        info = manager.analyze_structure(p)

        assert info["num_models"] >= 1
        assert len(info["chains"]) == 1
        assert info["chains"][0]["id"] == "A"

    def test_clean_pdb(self, mock_config, temp_workspace, dummy_pdb_content):
        """Test cleaning function."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace["cleaned"]

        # Input file
        raw_file = temp_workspace["raw"] / "1test.pdb"
        raw_file.write_text(dummy_pdb_content)

        success, _, cleaned_path = manager.clean_pdb(raw_file)

        assert success is True
        assert cleaned_path.exists()
        assert cleaned_path.parent == temp_workspace["cleaned"]

    def test_clean_pdb_reports_error_when_no_alpha_carbons_remain(
        self, mock_config, temp_workspace
    ):
        """Mustang only aligns protein structures - a chain with no CA
        atoms at all (e.g. non-protein content) must fail cleanly with a
        clear message, not silently produce an empty/unusable output."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace["cleaned"]

        raw_file = temp_workspace["raw"] / "no_ca.pdb"
        raw_file.write_text(
            "ATOM      1  N   ALA A   1      27.340  24.430   2.614  1.00  9.67           N  \n"
            "ATOM      2  C   ALA A   1      26.913  26.639   3.531  1.00  9.62           C  \n"
            "TER\n"
        )

        success, msg, cleaned_path = manager.clean_pdb(raw_file)

        assert success is False
        assert "0 Alpha Carbon" in msg
        assert cleaned_path is None

    def test_clean_pdb_prunes_low_plddt_for_alphafold_0_to_100_scale(
        self, mock_config, temp_workspace
    ):
        """AlphaFold structures encode per-residue pLDDT in the B-factor
        column on a 0-100 scale, so low-confidence residues (<50) should be
        pruned during cleaning."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace["cleaned"]

        content = (
            "ATOM      1  N   ALA A   1      11.104  13.203   7.334  1.00 90.00           N\n"
            "ATOM      2  CA  ALA A   1      12.104  14.203   8.334  1.00 90.00           C\n"
            "ATOM      3  N   GLY A   2      13.104  15.203   9.334  1.00 20.00           N\n"
            "ATOM      4  CA  GLY A   2      14.104  16.203  10.334  1.00 20.00           C\n"
            "TER"
        )
        raw_file = temp_workspace["raw"] / "af-p12345-f1.pdb"
        raw_file.write_text(content)

        success, _, cleaned_path = manager.clean_pdb(raw_file)

        assert success is True
        cleaned_content = cleaned_path.read_text()
        assert "ALA" in cleaned_content
        assert "GLY" not in cleaned_content  # pLDDT 20 < 50, pruned

    def test_clean_pdb_detects_0_to_1_plddt_scale_for_esmfold(
        self, mock_config, temp_workspace
    ):
        """Regression test: ESM Atlas structures write per-residue confidence
        as a 0-1 fraction, not AlphaFold's 0-100 scale (e.g. a real ESMFold
        structure's max B-factor was 0.96). Naively comparing that against
        the same "< 50" threshold used for AlphaFold would strip every
        residue (0.96 < 50), leaving zero CA atoms and silently failing the
        whole structure - this must auto-detect the scale instead."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace["cleaned"]

        content = (
            "ATOM      1  N   ALA A   1      11.104  13.203   7.334  1.00  0.90           N\n"
            "ATOM      2  CA  ALA A   1      12.104  14.203   8.334  1.00  0.90           C\n"
            "ATOM      3  N   GLY A   2      13.104  15.203   9.334  1.00  0.20           N\n"
            "ATOM      4  CA  GLY A   2      14.104  16.203  10.334  1.00  0.20           C\n"
            "TER"
        )
        raw_file = temp_workspace["raw"] / "esm-mgyp002537940442.pdb"
        raw_file.write_text(content)

        success, _, cleaned_path = manager.clean_pdb(raw_file)

        assert success is True
        cleaned_content = cleaned_path.read_text()
        assert (
            "ALA" in cleaned_content
        )  # pLDDT 0.90 scaled to 90, above the 50 threshold, kept
        assert (
            "GLY" not in cleaned_content
        )  # pLDDT 0.20 scaled to 20, below the threshold, pruned

    def test_clean_specific_chain(self, mock_config, temp_workspace):
        """Test cleaning a specific chain from a multi-chain PDB."""
        manager = PDBManager(mock_config)
        manager.cleaned_dir = temp_workspace["cleaned"]

        # Create multi-chain content with CA atoms
        multi_content = (
            "ATOM      1  N   ALA A   1      11.104  13.203   7.334  1.00 20.00           N\n"
            "ATOM      2  CA  ALA A   1      12.104  14.203   8.334  1.00 20.00           C\n"
            "TER\n"
            "ATOM      3  N   ALA B   1      21.104  23.203  17.334  1.00 20.00           N\n"
            "ATOM      4  CA  ALA B   1      22.104  24.203  18.334  1.00 20.00           C\n"
            "TER"
        )

        raw_file = temp_workspace["raw"] / "multi.pdb"
        raw_file.write_text(multi_content)

        # Clean only chain B
        success, _, cleaned_path = manager.clean_pdb(raw_file, chain="B")

        assert success is True
        content = cleaned_path.read_text()
        assert "ALA B" in content
        assert "ALA A" not in content

    def test_build_residue_renumber_map(self, mock_config, temp_workspace):
        """Raw residue numbers (which can start anywhere, e.g. 49) must map to
        the 1-based sequential numbers clean_pdb() assigns, since ligand/
        interaction analysis runs against the raw PDB while the 3D viewer
        shows the cleaned, renumbered structure Mustang actually aligned."""
        manager = PDBManager(mock_config)

        content = (
            "HETATM    1  O   HOH A  48      10.000  10.000  10.000  1.00 20.00           O\n"
            "ATOM      2  N   ALA A  49      11.104  13.203   7.334  1.00 20.00           N\n"
            "ATOM      3  CA  ALA A  49      12.104  14.203   8.334  1.00 20.00           C\n"
            "ATOM      4  N   GLY A  50      13.104  15.203   9.334  1.00 20.00           N\n"
            "ATOM      5  CA  GLY A  50      14.104  16.203  10.334  1.00 20.00           C\n"
            "HETATM    6  C1  RET A 401      15.104  17.203  11.334  1.00 20.00           C\n"
            "TER"
        )
        raw_file = temp_workspace["raw"] / "renumber_test.pdb"
        raw_file.write_text(content)

        mapping = manager.build_residue_renumber_map(
            raw_file, chain="A", remove_heteroatoms=True, remove_water=True
        )

        # Water (48) and the ligand (401, no CA) are stripped; the two
        # standard residues become sequential 1, 2.
        assert mapping == {49: 1, 50: 2}

    def test_build_residue_renumber_map_detects_0_to_1_plddt_scale_for_esmfold(
        self, mock_config, temp_workspace
    ):
        """Same 0-1 vs 0-100 pLDDT scale detection as clean_pdb() - without
        it, an esm- file's low-confidence residues (all bfactor <= 1.0)
        would be misread as universally below the 50 threshold and pruned."""
        manager = PDBManager(mock_config)

        content = (
            "ATOM      1  N   ALA A   1      11.104  13.203   7.334  1.00  0.90           N\n"
            "ATOM      2  CA  ALA A   1      12.104  14.203   8.334  1.00  0.90           C\n"
            "ATOM      3  N   GLY A   2      13.104  15.203   9.334  1.00  0.20           N\n"
            "ATOM      4  CA  GLY A   2      14.104  16.203  10.334  1.00  0.20           C\n"
            "TER"
        )
        raw_file = temp_workspace["raw"] / "esm-mgyp002537940442.pdb"
        raw_file.write_text(content)

        mapping = manager.build_residue_renumber_map(
            raw_file, chain="A", remove_heteroatoms=True, remove_water=True
        )

        # Only ALA (0.90 * 100 = 90 >= 50) survives; GLY (20) is pruned.
        assert mapping == {1: 1}

    def test_build_residue_renumber_map_returns_empty_on_parse_failure(
        self, mock_config, temp_workspace
    ):
        manager = PDBManager(mock_config)

        mapping = manager.build_residue_renumber_map(
            temp_workspace["raw"] / "does_not_exist.pdb"
        )

        assert mapping == {}

    def test_build_residue_renumber_map_returns_empty_when_chain_not_found(
        self, mock_config, temp_workspace
    ):
        manager = PDBManager(mock_config)
        content = (
            "ATOM      1  N   ALA A  49      11.104  13.203   7.334  1.00 20.00           N\n"
            "ATOM      2  CA  ALA A  49      12.104  14.203   8.334  1.00 20.00           C\n"
            "TER"
        )
        raw_file = temp_workspace["raw"] / "single_chain.pdb"
        raw_file.write_text(content)

        mapping = manager.build_residue_renumber_map(raw_file, chain="Z")

        assert mapping == {}

    def test_save_uploaded_bytes_saves_and_validates_a_real_structure(
        self, mock_config, temp_workspace, dummy_pdb_content
    ):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, _, path = manager.save_uploaded_bytes(
            "my_structure.pdb", dummy_pdb_content.encode(), "UPLOAD-ABCD1234"
        )

        assert success is True
        assert path == temp_workspace["raw"] / "upload-abcd1234.pdb"
        assert path.exists()
        assert path.read_bytes() == dummy_pdb_content.encode()

    def test_save_uploaded_bytes_rejects_content_that_isnt_a_real_structure(
        self, mock_config, temp_workspace
    ):
        """A .pdb-named file with no actual structure content must fail
        clearly here, not silently reach Mustang later."""
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, msg, path = manager.save_uploaded_bytes(
            "not_a_structure.pdb",
            b"this is just a text file, not a PDB",
            "UPLOAD-BADCONTENT",
        )

        assert success is False
        assert "parse" in msg.lower()
        assert path is None
        # The invalid file must not be left behind for a later
        # download_pdb() cache-hit check to mistake for a real structure.
        assert not (temp_workspace["raw"] / "upload-badcontent.pdb").exists()

    def test_save_uploaded_bytes_rejects_oversized_content(
        self, mock_config, temp_workspace, dummy_pdb_content
    ):
        """mock_config sets pdb.max_file_size_mb to 10."""
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        oversized = b"x" * (11 * 1024 * 1024)
        success, msg, path = manager.save_uploaded_bytes(
            "huge.pdb", oversized, "UPLOAD-TOOBIG"
        )

        assert success is False
        assert "too large" in msg.lower()
        assert path is None
        assert not (temp_workspace["raw"] / "upload-toobig.pdb").exists()

    def test_save_uploaded_bytes_preserves_cif_extension(
        self, mock_config, temp_workspace
    ):
        """A .cif upload must be saved with a .cif extension (not forced to
        .pdb) so _get_structure() picks MMCIFParser, not PDBParser, when
        it's later analyzed/downloaded-as-cached."""
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        with patch.object(manager, "_get_structure") as mock_get_structure:
            mock_model = [object()]  # one "chain"
            mock_get_structure.return_value = [mock_model]

            success, _, path = manager.save_uploaded_bytes(
                "my_model.cif", b"data_test\n...", "UPLOAD-CIFTEST"
            )

        assert success is True
        assert path == temp_workspace["raw"] / "upload-ciftest.cif"
        assert path.exists()

    def test_download_pdb_finds_an_uploaded_file_under_its_real_extension(
        self, mock_config, temp_workspace
    ):
        """detect_source() doesn't recognize "UPLOAD-" IDs, so download_pdb()
        defaults to a .pdb extension guess - but an uploaded structure may
        actually be a .cif. It must find the real file instead of trying to
        (and failing to) fetch a remote source that was never the origin."""
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        cif_file = temp_workspace["raw"] / "upload-realcif.cif"
        cif_file.write_text("data_test\n...")

        success, _, path = asyncio.run(manager.download_pdb("UPLOAD-REALCIF"))

        assert success is True
        assert path == cif_file

    def test_download_pdb_rejects_invalid_id_format(self, mock_config, temp_workspace):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, msg, path = asyncio.run(manager.download_pdb("not_a_valid_id!!"))

        assert success is False
        assert path is None

    def test_download_pdb_uses_cached_local_file_without_a_network_call(
        self, mock_config, temp_workspace
    ):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]
        (temp_workspace["raw"] / "4rlt.pdb").write_text("ATOM")

        with patch("httpx.AsyncClient.get") as mock_get:
            success, msg, path = asyncio.run(manager.download_pdb("4RLT"))

        assert success is True
        assert "local file" in msg.lower()
        mock_get.assert_not_called()

    @patch("httpx.AsyncClient.get")
    def test_download_pdb_standard_pdb_success(
        self, mock_get, mock_config, temp_workspace
    ):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"ATOM real pdb content"
        mock_get.return_value = mock_response

        success, msg, path = asyncio.run(manager.download_pdb("4RLT"))

        assert success is True
        assert path.exists()
        assert path.read_bytes() == b"ATOM real pdb content"

    @patch("httpx.AsyncClient.get")
    def test_download_pdb_standard_pdb_not_found(
        self, mock_get, mock_config, temp_workspace
    ):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        success, msg, path = asyncio.run(manager.download_pdb("9ZZZ"))

        assert success is False
        assert path is None

    @patch("httpx.AsyncClient.get")
    def test_download_pdb_alphafold_falls_back_across_versions(
        self, mock_get, mock_config, temp_workspace
    ):
        """v6 (the default first attempt) 404s, v4 succeeds - must not give
        up after the first version fails."""
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        responses = []
        for v in ["6"]:
            r = MagicMock()
            r.status_code = 404
            responses.append(r)
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.content = b"cif data"
        responses.append(success_response)
        mock_get.side_effect = responses

        success, msg, path = asyncio.run(manager.download_pdb("AF-P69905-F1"))

        assert success is True
        assert path.suffix == ".cif"

    @patch("httpx.AsyncClient.get")
    def test_download_pdb_alphafold_all_versions_fail(
        self, mock_get, mock_config, temp_workspace
    ):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        not_found = MagicMock()
        not_found.status_code = 404
        mock_get.return_value = not_found

        success, msg, path = asyncio.run(manager.download_pdb("AF-P69905-F1"))

        assert success is False
        assert path is None
        assert "AlphaFold" in msg

    @patch("httpx.AsyncClient.get")
    def test_download_pdb_swissmodel_success(
        self, mock_get, mock_config, temp_workspace
    ):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"swiss model pdb"
        mock_get.return_value = mock_response

        success, msg, path = asyncio.run(manager.download_pdb("SM-P69905"))

        assert success is True
        assert path.exists()

    @patch("httpx.AsyncClient.get")
    def test_download_pdb_esmfold_success(self, mock_get, mock_config, temp_workspace):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"esm predicted structure"
        mock_get.return_value = mock_response

        success, msg, path = asyncio.run(manager.download_pdb("ESM-MGYP002537940442"))

        assert success is True
        assert path.exists()

    @patch("httpx.AsyncClient.get", side_effect=Exception("connection reset"))
    def test_download_pdb_network_exception_reported_not_raised(
        self, mock_get, mock_config, temp_workspace
    ):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, msg, path = asyncio.run(manager.download_pdb("4RLT"))

        assert success is False
        assert path is None


class TestSaveUploadedFile:
    """save_uploaded_file() - the Streamlit UploadedFile-shaped counterpart
    to save_uploaded_bytes() (the SPA/API upload path)."""

    def test_saves_uploaded_file_content(self, mock_config, temp_workspace):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        fake_upload = MagicMock()
        fake_upload.name = "my structure.pdb"
        fake_upload.getbuffer.return_value = b"ATOM uploaded content"

        success, msg, path = manager.save_uploaded_file(fake_upload)

        assert success is True
        assert path.name == "my_structure.pdb"
        assert path.read_bytes() == b"ATOM uploaded content"

    def test_reports_failure_without_raising(self, mock_config, temp_workspace):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        fake_upload = MagicMock()
        fake_upload.name = "test.pdb"
        fake_upload.getbuffer.side_effect = OSError("disk full")

        success, msg, path = manager.save_uploaded_file(fake_upload)

        assert success is False
        assert path is None


class TestBatchClean:
    def test_cleans_multiple_files_and_reports_per_file_results(
        self, mock_config, temp_workspace, dummy_pdb_content
    ):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]
        manager.cleaned_dir = temp_workspace["cleaned"]

        files = []
        for name in ["a.pdb", "b.pdb"]:
            f = temp_workspace["raw"] / name
            f.write_text(dummy_pdb_content)
            files.append(f)

        results = manager.batch_clean(files)

        assert set(results.keys()) == {"a.pdb", "b.pdb"}
        assert all(r[0] is True for r in results.values())

    def test_a_single_file_failure_does_not_abort_the_batch(
        self, mock_config, temp_workspace, dummy_pdb_content
    ):
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]
        manager.cleaned_dir = temp_workspace["cleaned"]

        good_file = temp_workspace["raw"] / "good.pdb"
        good_file.write_text(dummy_pdb_content)
        bad_file = temp_workspace["raw"] / "does_not_exist.pdb"

        results = manager.batch_clean([good_file, bad_file])

        assert results["good.pdb"][0] is True

    def test_reports_a_genuinely_unexpected_exception_from_the_worker(
        self, mock_config, temp_workspace, dummy_pdb_content
    ):
        """clean_pdb() already handles its own expected failures internally
        (returning a (False, msg, None) tuple) - this covers the outer
        try/except around future.result() itself, for an exception that
        somehow escapes clean_pdb() rather than being caught by it."""
        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]
        manager.cleaned_dir = temp_workspace["cleaned"]

        pdb_file = temp_workspace["raw"] / "boom.pdb"
        pdb_file.write_text(dummy_pdb_content)

        with patch.object(manager, "clean_pdb", side_effect=RuntimeError("boom")):
            results = manager.batch_clean([pdb_file])

        assert results["boom.pdb"][0] is False
        assert "boom" in results["boom.pdb"][1]


class TestCleanSelect:
    """Direct unit tests for _CleanSelect's Bio.PDB.Select-duck-typed
    methods - clean_pdb()'s existing tests exercise these indirectly
    through a real PDBIO.save() call, which doesn't guarantee every
    branch (e.g. accept_model/accept_chain always return 1 and may not
    even be invoked by every Bio.PDB version's save() path)."""

    def _select(
        self,
        is_plddt_model=False,
        plddt_scale=1.0,
        remove_water=True,
        remove_heteroatoms=True,
    ):
        from src.backend.pdb_manager import _CleanSelect

        return _CleanSelect(
            is_plddt_model, plddt_scale, remove_water, remove_heteroatoms
        )

    def test_accept_model_always_keeps(self):
        assert self._select().accept_model(object()) == 1

    def test_accept_chain_always_keeps(self):
        assert self._select().accept_chain(object()) == 1

    def test_accept_atom_excludes_hydrogen_by_element(self):
        atom = MagicMock(element="H")
        atom.name = "H1"
        assert self._select().accept_atom(atom) == 0

    def test_accept_atom_excludes_hydrogen_by_name_prefix(self):
        atom = MagicMock(element="")
        atom.name = "HB2"
        assert self._select().accept_atom(atom) == 0

    def test_accept_atom_keeps_non_hydrogen(self):
        atom = MagicMock(element="C")
        atom.name = "CA"
        assert self._select().accept_atom(atom) == 1

    def test_below_plddt_threshold_false_on_attribute_error(self):
        residue = MagicMock()
        residue.get_atoms.side_effect = AttributeError("no atoms")
        select = self._select(is_plddt_model=True, plddt_scale=1.0)
        assert select._below_plddt_threshold(residue) is False

    def test_below_plddt_threshold_false_when_no_atoms(self):
        residue = MagicMock()
        residue.get_atoms.return_value = iter([])
        select = self._select(is_plddt_model=True, plddt_scale=1.0)
        assert select._below_plddt_threshold(residue) is False

    def test_accept_residue_keeps_hetatm_with_a_ca_atom(self):
        """A non-standard residue (e.g. a modified amino acid) with a CA
        atom is still part of the protein backbone, so it's kept even when
        remove_heteroatoms is True - unlike a true ligand/ion, which has
        no CA at all."""
        residue = MagicMock()
        residue.id = ("H_MSE", 5, " ")
        residue.resname = "MSE"
        residue.has_id.return_value = True

        select = self._select(remove_water=True, remove_heteroatoms=True)

        assert select.accept_residue(residue) == 1


class TestFetchAlphafoldResponse:
    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_timeout_reports_clean_failure(self, mock_get, mock_config):
        mock_get.side_effect = httpx.TimeoutException("timed out")
        manager = PDBManager(mock_config)

        async with httpx.AsyncClient() as client:
            success, msg, response = await manager._fetch_alphafold_response(
                "AF-P69905-F1", client, manage_client=False
            )

        assert success is False
        assert "timeout" in msg.lower()
        assert response is None

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_unexpected_exception_reports_clean_failure(
        self, mock_get, mock_config
    ):
        mock_get.side_effect = RuntimeError("boom")
        manager = PDBManager(mock_config)

        async with httpx.AsyncClient() as client:
            success, msg, response = await manager._fetch_alphafold_response(
                "AF-P69905-F1", client, manage_client=False
            )

        assert success is False
        assert "boom" in msg
        assert response is None


class TestFetchSwissmodelResponse:
    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_unexpected_exception_reports_clean_failure(
        self, mock_get, mock_config
    ):
        mock_get.side_effect = RuntimeError("boom")
        manager = PDBManager(mock_config)

        async with httpx.AsyncClient() as client:
            success, msg, response = await manager._fetch_swissmodel_response(
                "SM-P69905", client, manage_client=False
            )

        assert success is False
        assert "boom" in msg
        assert response is None


class TestBatchDownload:
    @pytest.mark.asyncio
    async def test_downloads_all_ids_in_parallel_and_maps_results(self, mock_config):
        manager = PDBManager(mock_config)

        async def fake_download(pdb_id, force=False, client=None):
            return True, "ok", Path(f"/fake/{pdb_id}.pdb")

        with patch.object(manager, "download_pdb", side_effect=fake_download):
            results = await manager.batch_download(["4RLT", "3UG9"])

        assert set(results.keys()) == {"4RLT", "3UG9"}
        assert all(r[0] is True for r in results.values())

    @pytest.mark.asyncio
    async def test_a_single_failure_does_not_abort_the_batch(self, mock_config):
        manager = PDBManager(mock_config)

        async def fake_download(pdb_id, force=False, client=None):
            if pdb_id == "9ZZZ":
                return False, "404 Not Found", None
            return True, "ok", Path(f"/fake/{pdb_id}.pdb")

        with patch.object(manager, "download_pdb", side_effect=fake_download):
            results = await manager.batch_download(["4RLT", "9ZZZ"])

        assert results["4RLT"][0] is True
        assert results["9ZZZ"][0] is False


class TestDownloadPdbSaveHandling:
    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_registers_with_cache_manager_on_success(
        self, mock_get, mock_config, temp_workspace
    ):
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b"ATOM"
        mock_get.return_value = mock_response

        cache_manager = MagicMock()
        manager = PDBManager(mock_config, cache_manager=cache_manager)
        manager.raw_dir = temp_workspace["raw"]

        await manager.download_pdb("1A0J")

        cache_manager.register_item.assert_called_once()
        assert cache_manager.register_item.call_args[0][0] == "1A0J"

    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    @patch("src.backend.pdb_manager._write_bytes")
    async def test_save_failure_reports_clean_error(
        self, mock_write, mock_get, mock_config, temp_workspace
    ):
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = b"ATOM"
        mock_get.return_value = mock_response
        mock_write.side_effect = OSError("disk full")

        manager = PDBManager(mock_config)
        manager.raw_dir = temp_workspace["raw"]

        success, msg, path = await manager.download_pdb("1A0J")

        assert success is False
        assert "disk full" in msg
        assert path is None


class TestFetchEsmfoldResponse:
    @pytest.mark.asyncio
    @patch("src.backend.pdb_manager.httpx.AsyncClient.get")
    async def test_unexpected_exception_reports_clean_failure(
        self, mock_get, mock_config
    ):
        mock_get.side_effect = RuntimeError("boom")
        manager = PDBManager(mock_config)

        async with httpx.AsyncClient() as client:
            success, msg, response = await manager._fetch_esmfold_response(
                "ESM-MGYP001", client, manage_client=False
            )

        assert success is False
        assert "boom" in msg
        assert response is None
