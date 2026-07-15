from unittest.mock import Mock, patch

import httpx
import pytest

from src.backend.validation_service import fetch_pdbe_validation


def _mock_response(status_code=200, json_data=None):
    mock = Mock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    return mock


class TestFetchPdbeValidation:
    @pytest.mark.asyncio
    @patch("src.backend.validation_service.httpx.AsyncClient.get")
    async def test_parses_all_three_metrics(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={
                "4hhb": {
                    "clashscore": {
                        "rawvalue": 141.11,
                        "absolute": 0.0,
                        "relative": 0.0,
                    },
                    "percent-rama-outliers": {
                        "rawvalue": 1.24,
                        "absolute": 12.8,
                        "relative": 2.6,
                    },
                    "percent-rota-outliers": {
                        "rawvalue": 8.44,
                        "absolute": 10.6,
                        "relative": 1.3,
                    },
                }
            }
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_pdbe_validation("4HHB", client)

        assert result == {
            "clashscore": {
                "value": 141.11,
                "percentile_archive": 0.0,
                "percentile_similar_resolution": 0.0,
            },
            "percent_rama_outliers": {
                "value": 1.24,
                "percentile_archive": 12.8,
                "percentile_similar_resolution": 2.6,
            },
            "percent_rota_outliers": {
                "value": 8.44,
                "percentile_archive": 10.6,
                "percentile_similar_resolution": 1.3,
            },
        }

    @pytest.mark.asyncio
    @patch("src.backend.validation_service.httpx.AsyncClient.get")
    async def test_lowercases_the_pdb_id_for_the_lookup_key(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={"1crn": {"clashscore": {"rawvalue": 0.0}}}
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_pdbe_validation("1CRN", client)
        assert result["clashscore"]["value"] == 0.0

    @pytest.mark.asyncio
    @patch("src.backend.validation_service.httpx.AsyncClient.get")
    async def test_skips_a_metric_missing_rawvalue(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={"4hhb": {"clashscore": {"absolute": 5.0}}}
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_pdbe_validation("4HHB", client)
        assert result is None

    @pytest.mark.asyncio
    @patch("src.backend.validation_service.httpx.AsyncClient.get")
    async def test_returns_none_when_entry_not_found(self, mock_get):
        mock_get.return_value = _mock_response(json_data={})
        async with httpx.AsyncClient() as client:
            result = await fetch_pdbe_validation("9ZZZ", client)
        assert result is None

    @pytest.mark.asyncio
    @patch("src.backend.validation_service.httpx.AsyncClient.get")
    async def test_rejects_an_unsafe_pdb_id_without_making_a_request(self, mock_get):
        async with httpx.AsyncClient() as client:
            result = await fetch_pdbe_validation("../etc/passwd", client)
        assert result is None
        mock_get.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.backend.validation_service.httpx.AsyncClient.get")
    async def test_rejects_a_pdb_id_that_would_redirect_the_request_path(
        self, mock_get
    ):
        async with httpx.AsyncClient() as client:
            result = await fetch_pdbe_validation("4hhb/../../evil", client)
        assert result is None
        mock_get.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.backend.validation_service.httpx.AsyncClient.get")
    async def test_returns_none_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(status_code=404)
        async with httpx.AsyncClient() as client:
            result = await fetch_pdbe_validation("9ZZZ", client)
        assert result is None

    @pytest.mark.asyncio
    @patch("src.backend.validation_service.httpx.AsyncClient.get")
    async def test_returns_none_on_http_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        async with httpx.AsyncClient() as client:
            result = await fetch_pdbe_validation("4HHB", client)
        assert result is None

    @pytest.mark.asyncio
    @patch("src.backend.validation_service.httpx.AsyncClient.get")
    async def test_returns_none_on_malformed_json(self, mock_get):
        mock = Mock()
        mock.status_code = 200
        mock.json.side_effect = ValueError("not json")
        mock_get.return_value = mock
        async with httpx.AsyncClient() as client:
            result = await fetch_pdbe_validation("4HHB", client)
        assert result is None
