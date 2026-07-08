from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from src.backend.pdb_manager import PDBManager


def _resp(status_code=200, json_data=None):
    response = AsyncMock()
    response.status_code = status_code
    response.json = MagicMock(return_value=json_data or {})
    return response


class TestClassifyPdbIds:
    def test_splits_ids_by_source_and_dedupes(self):
        result = PDBManager._classify_pdb_ids(
            ["4rlt", "4RLT", "AF-P12345-F1", "SM-P67890", "ESM-MGYP001"]
        )
        original_to_base, unique_base_ids, af_ids, sm_ids, esm_ids = result

        assert set(unique_base_ids) == {"4RLT"}
        assert af_ids == ["AF-P12345-F1"]
        assert sm_ids == ["SM-P67890"]
        assert esm_ids == ["ESM-MGYP001"]

    def test_preserves_original_casing_as_mapping_key(self):
        original_to_base, *_ = PDBManager._classify_pdb_ids(["4rlt"])
        assert original_to_base == {"4rlt": "4RLT"}

    def test_chain_variants_map_to_the_same_base_id(self):
        # Real PDB IDs are exactly 4 chars; anything appended is truncated,
        # so two "variants" of the same entry share one base id.
        original_to_base, unique_base_ids, *_ = PDBManager._classify_pdb_ids(
            ["4RLTA", "4RLTB"]
        )
        assert original_to_base == {"4RLTA": "4RLT", "4RLTB": "4RLT"}
        assert unique_base_ids == ["4RLT"]


class TestParseRcsbEntry:
    def test_parses_full_entry(self):
        entry = {
            "struct": {"title": "Crystal structure of X"},
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
            "rcsb_entry_info": {"resolution_combined": [1.85]},
            "polymer_entities": [
                {"rcsb_entity_source_organism": [{"scientific_name": "Homo sapiens"}]}
            ],
        }
        result = PDBManager._parse_rcsb_entry(entry)
        assert result == {
            "title": "Crystal structure of X",
            "method": "X-RAY DIFFRACTION",
            "resolution": "1.85 Å",
            "organism": "Homo sapiens",
        }

    def test_missing_fields_fall_back_to_na(self):
        result = PDBManager._parse_rcsb_entry({})
        assert result == {
            "title": "N/A",
            "method": "N/A",
            "resolution": "N/A",
            "organism": "N/A",
        }


class TestEsmMetadata:
    def test_builds_fixed_fields_per_id(self):
        result = PDBManager._esm_metadata(["ESM-MGYP001"])
        assert result == {
            "ESM-MGYP001": {
                "title": "[ESMFold] MGYP001",
                "method": "Predicted (ESMFold)",
                "resolution": "pLDDT Scored",
                "organism": "Metagenomic (unclassified)",
            }
        }


class TestRemapMetadataToOriginalIds:
    def test_exact_match(self):
        manager = PDBManager.__new__(PDBManager)
        result = manager._remap_metadata_to_original_ids(
            {"4rlt": "4RLT"}, {"4RLT": {"title": "X"}}
        )
        assert result == {"4rlt": {"title": "X"}}

    def test_falls_back_to_uppercase_match(self):
        manager = PDBManager.__new__(PDBManager)
        result = manager._remap_metadata_to_original_ids(
            {"af-p1": "af-p1"}, {"AF-P1": {"title": "Y"}}
        )
        assert result == {"af-p1": {"title": "Y"}}

    def test_no_match_returns_empty_metadata(self):
        manager = PDBManager.__new__(PDBManager)
        result = manager._remap_metadata_to_original_ids({"4rlt": "4RLT"}, {})
        assert result == {"4rlt": PDBManager._empty_metadata()}


@pytest.mark.asyncio
class TestFetchUniprotNameOrganism:
    async def test_uses_recommended_name(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.get.return_value = _resp(
            json_data={
                "proteinDescription": {
                    "recommendedName": {"fullName": {"value": "Hemoglobin"}}
                },
                "organism": {"scientificName": "Homo sapiens"},
            }
        )

        name, organism = await manager._fetch_uniprot_name_organism(
            client, "P12345", "fallback"
        )

        assert name == "Hemoglobin"
        assert organism == "Homo sapiens"

    async def test_falls_back_to_submission_name(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.get.return_value = _resp(
            json_data={
                "proteinDescription": {
                    "submissionNames": [{"fullName": {"value": "Submitted Name"}}]
                },
                "organism": {"scientificName": "Mus musculus"},
            }
        )

        name, organism = await manager._fetch_uniprot_name_organism(
            client, "P12345", "fallback"
        )

        assert name == "Submitted Name"
        assert organism == "Mus musculus"

    async def test_falls_back_to_gene_name_when_no_description_name(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.get.return_value = _resp(
            json_data={
                "proteinDescription": {},
                "genes": [{"geneName": {"value": "HBB"}}],
                "organism": {"scientificName": "Homo sapiens"},
            }
        )

        name, organism = await manager._fetch_uniprot_name_organism(
            client, "P12345", "fallback"
        )

        assert name == "HBB"

    async def test_non_200_returns_fallback(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.get.return_value = _resp(status_code=404)

        name, organism = await manager._fetch_uniprot_name_organism(
            client, "P12345", "fallback name"
        )

        assert name == "fallback name"
        assert organism == "N/A"

    async def test_exception_returns_fallback(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.get.side_effect = httpx.ConnectError("no route")

        name, organism = await manager._fetch_uniprot_name_organism(
            client, "P12345", "fallback name"
        )

        assert name == "fallback name"
        assert organism == "N/A"


@pytest.mark.asyncio
class TestFetchRcsbMetadata:
    async def test_empty_ids_returns_empty_without_calling_api(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()

        result = await manager._fetch_rcsb_metadata(client, [])

        assert result == {}
        client.post.assert_not_called()

    async def test_non_200_returns_empty(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.post.return_value = _resp(status_code=500)

        result = await manager._fetch_rcsb_metadata(client, ["4RLT"])

        assert result == {}

    async def test_parses_entries_keyed_by_rcsb_id(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.post.return_value = _resp(
            json_data={
                "data": {
                    "entries": [
                        {
                            "rcsb_id": "4RLT",
                            "struct": {"title": "Some Structure"},
                            "exptl": [{"method": "X-RAY DIFFRACTION"}],
                            "rcsb_entry_info": {"resolution_combined": [2.1]},
                            "polymer_entities": [],
                        }
                    ]
                }
            }
        )

        result = await manager._fetch_rcsb_metadata(client, ["4RLT"])

        assert result["4RLT"]["title"] == "Some Structure"
        assert result["4RLT"]["resolution"] == "2.10 Å"


@pytest.mark.asyncio
class TestFetchAlphafoldMetadata:
    async def test_builds_title_from_uniprot_lookup(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        with patch.object(
            manager,
            "_fetch_uniprot_name_organism",
            AsyncMock(return_value=("Hemoglobin", "Homo sapiens")),
        ):
            result = await manager._fetch_alphafold_metadata(client, ["AF-P12345-F1"])

        assert result["AF-P12345-F1"]["title"] == "[AlphaFold] Hemoglobin"
        assert result["AF-P12345-F1"]["method"] == "Predicted (AF2)"
        assert result["AF-P12345-F1"]["organism"] == "Homo sapiens"

    async def test_skips_malformed_id_without_uniprot_segment(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()

        result = await manager._fetch_alphafold_metadata(client, ["AF"])

        assert result == {}


@pytest.mark.asyncio
class TestFetchSwissmodelRepositoryInfo:
    async def test_template_and_coverage_reported(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.get.return_value = _resp(
            json_data={
                "result": {
                    "structures": [
                        {
                            "method": "Homology model",
                            "template": "1abc",
                            "coverage": 0.87,
                        }
                    ]
                }
            }
        )

        method, resolution = await manager._fetch_swissmodel_repository_info(
            client, "P12345", "SM-P12345"
        )

        assert method == "Homology model"
        assert resolution == "Template 1abc (87% cov.)"

    async def test_no_models_returns_defaults(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.get.return_value = _resp(json_data={"result": {"structures": []}})

        method, resolution = await manager._fetch_swissmodel_repository_info(
            client, "P12345", "SM-P12345"
        )

        assert method == "Homology model"
        assert resolution == "N/A"

    async def test_exception_returns_defaults(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()
        client.get.side_effect = httpx.ConnectError("no route")

        method, resolution = await manager._fetch_swissmodel_repository_info(
            client, "P12345", "SM-P12345"
        )

        assert method == "Homology model"
        assert resolution == "N/A"


@pytest.mark.asyncio
class TestFetchMetadataEndToEnd:
    async def test_empty_batch_returns_empty(self, mock_config):
        manager = PDBManager(mock_config)
        assert await manager.fetch_metadata([]) == {}

    async def test_mixed_batch_routes_each_id_to_its_source(self, mock_config):
        manager = PDBManager(mock_config)
        client = AsyncMock()

        def fake_post(url, json=None, **kwargs):
            return _resp(
                json_data={
                    "data": {
                        "entries": [
                            {
                                "rcsb_id": "4RLT",
                                "struct": {"title": "Real Structure"},
                                "exptl": [{"method": "X-RAY DIFFRACTION"}],
                                "rcsb_entry_info": {"resolution_combined": [1.5]},
                                "polymer_entities": [],
                            }
                        ]
                    }
                }
            )

        client.post.side_effect = fake_post

        with patch.object(
            manager,
            "_fetch_uniprot_name_organism",
            AsyncMock(return_value=("A Protein", "Homo sapiens")),
        ), patch.object(
            manager,
            "_fetch_swissmodel_repository_info",
            AsyncMock(return_value=("Homology model", "N/A")),
        ):
            result = await manager.fetch_metadata(
                ["4RLT", "AF-P12345-F1", "SM-P67890", "ESM-MGYP001"], client=client
            )

        assert result["4RLT"]["title"] == "Real Structure"
        assert result["AF-P12345-F1"]["title"] == "[AlphaFold] A Protein"
        assert result["SM-P67890"]["title"] == "[SWISS-MODEL] A Protein"
        assert result["ESM-MGYP001"]["title"] == "[ESMFold] MGYP001"

    async def test_critical_failure_falls_back_to_empty_metadata_for_all_ids(
        self, mock_config
    ):
        manager = PDBManager(mock_config)
        with patch.object(
            manager, "_fetch_rcsb_metadata", side_effect=RuntimeError("boom")
        ):
            result = await manager.fetch_metadata(["4RLT", "3UG9"])

        assert result == {
            "4RLT": PDBManager._empty_metadata(),
            "3UG9": PDBManager._empty_metadata(),
        }
