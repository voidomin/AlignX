from unittest.mock import patch, AsyncMock

import httpx
import pytest

from src.backend.esmfold_client import fold_sequence, ESMFoldError


def _mock_response(status_code=200, text=""):
    response = AsyncMock()
    response.status_code = status_code
    response.text = text
    return response


class TestFoldSequence:
    @pytest.mark.asyncio
    @patch("src.backend.esmfold_client.httpx.AsyncClient.post")
    async def test_returns_the_real_pdb_text_on_success(self, mock_post):
        mock_post.return_value = _mock_response(
            text="HEADER\nATOM      1  N   MET A   1\nEND\n"
        )
        async with httpx.AsyncClient() as client:
            result = await fold_sequence("MVHLTPEEKSAVTALWGKVNV", client)

        assert "ATOM" in result
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["content"] == "MVHLTPEEKSAVTALWGKVNV"

    @pytest.mark.asyncio
    @patch("src.backend.esmfold_client.httpx.AsyncClient.post")
    async def test_raises_on_non_200_status(self, mock_post):
        mock_post.return_value = _mock_response(status_code=504, text="timeout")
        async with httpx.AsyncClient() as client:
            with pytest.raises(ESMFoldError, match="504"):
                await fold_sequence("MVHLTPEEKSAVTALWGKVNV", client)

    @pytest.mark.asyncio
    @patch("src.backend.esmfold_client.httpx.AsyncClient.post")
    async def test_raises_when_response_has_no_atom_records(self, mock_post):
        mock_post.return_value = _mock_response(text="{}")
        async with httpx.AsyncClient() as client:
            with pytest.raises(ESMFoldError, match="no usable structure"):
                await fold_sequence("MVHLTPEEKSAVTALWGKVNV", client)

    @pytest.mark.asyncio
    @patch("src.backend.esmfold_client.httpx.AsyncClient.post")
    async def test_raises_on_a_connection_error(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("boom")
        async with httpx.AsyncClient() as client:
            with pytest.raises(ESMFoldError, match="request failed"):
                await fold_sequence("MVHLTPEEKSAVTALWGKVNV", client)

    @pytest.mark.asyncio
    @patch("src.backend.esmfold_client.httpx.AsyncClient.post")
    async def test_manages_its_own_client_when_none_given(self, mock_post):
        mock_post.return_value = _mock_response(text="ATOM      1  N   MET A   1\n")
        result = await fold_sequence("MVHLTPEEKSAVTALWGKVNV")
        assert "ATOM" in result
