import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.launch_desktop import _open_browser_delayed, main, print_banner


def test_print_banner(capsys):
    print_banner()
    captured = capsys.readouterr()
    assert "StructScope Desktop Edition" in captured.out
    assert "100% Local" in captured.out


@patch("webbrowser.open")
@patch("time.sleep")
def test_open_browser_delayed(mock_sleep, mock_browser):
    _open_browser_delayed()
    mock_sleep.assert_called_once_with(1.2)
    mock_browser.assert_called_once_with("http://127.0.0.1:8000")


@patch("webbrowser.open")
@patch("threading.Thread")
@patch("sys.exit")
def test_main_runs_uvicorn(mock_exit, mock_thread, mock_browser, capsys):
    mock_uvicorn = MagicMock()
    with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
        main()
        captured = capsys.readouterr()
        assert "Starting StructScope Desktop server" in captured.out
        mock_uvicorn.run.assert_called_once_with(
            "src.backend.api:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
            log_level="info",
        )
        mock_thread.assert_called_once()


@patch("sys.exit")
def test_main_handles_missing_uvicorn(mock_exit, capsys):
    with patch.dict("sys.modules", {"uvicorn": None}):
        main()
        captured = capsys.readouterr()
        assert "ERROR: 'uvicorn' is not installed" in captured.out
        mock_exit.assert_called_once_with(1)
