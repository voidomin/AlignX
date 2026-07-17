import importlib.util
import json
from pathlib import Path

import httpx

_CLI_PATH = Path(__file__).resolve().parent.parent / "scripts" / "structscope_cli.py"
_spec = importlib.util.spec_from_file_location("structscope_cli", _CLI_PATH)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


def _install_mock_transport(monkeypatch, handler):
    """Makes every httpx.Client(...) the CLI constructs route through a
    MockTransport instead of real sockets - no new mocking dependency
    (respx isn't installed), just httpx's own built-in test transport."""
    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client

    def _client(*, base_url, timeout=None):
        return real_client_cls(base_url=base_url, transport=transport)

    monkeypatch.setattr(cli.httpx, "Client", _client)


def test_align_without_wait_submits_and_returns_immediately(monkeypatch, capsys):
    def handler(request):
        assert request.url.path == "/api/jobs/align"
        body = json.loads(request.content)
        assert body["pdb_ids"] == ["4HHB", "2HHB"]
        assert body["remove_water"] is True
        return httpx.Response(202, json={"job_id": "job1", "status": "queued"})

    _install_mock_transport(monkeypatch, handler)

    parser = cli.build_parser()
    args = parser.parse_args(["align", "4HHB", "2HHB"])
    exit_code = args.func(args)

    assert exit_code == 0
    assert "Submitted job job1" in capsys.readouterr().out


def test_align_with_wait_polls_to_completion_and_downloads_report(
    monkeypatch, capsys, tmp_path
):
    calls = {"polls": 0}

    def handler(request):
        if request.url.path == "/api/jobs/align":
            return httpx.Response(202, json={"job_id": "job1", "status": "queued"})
        if request.url.path == "/api/jobs/job1":
            calls["polls"] += 1
            if calls["polls"] < 2:
                return httpx.Response(200, json={"status": "running"})
            return httpx.Response(
                200, json={"status": "completed", "results": {"id": "run_abc"}}
            )
        if request.url.path == "/api/report":
            assert request.url.params["run_id"] == "run_abc"
            return httpx.Response(200, content=b"%PDF-1.4 mock report")
        raise AssertionError(f"unexpected path {request.url.path}")

    _install_mock_transport(monkeypatch, handler)

    report_path = tmp_path / "out.pdf"
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "align",
            "4HHB",
            "2HHB",
            "--wait",
            "--poll-interval",
            "0",
            "--report",
            str(report_path),
        ]
    )
    exit_code = args.func(args)

    assert exit_code == 0
    assert report_path.read_bytes() == b"%PDF-1.4 mock report"
    assert "Alignment complete - run_id: run_abc" in capsys.readouterr().out


def test_align_with_wait_reports_a_failed_job(monkeypatch, capsys):
    def handler(request):
        if request.url.path == "/api/jobs/align":
            return httpx.Response(202, json={"job_id": "job1", "status": "queued"})
        if request.url.path == "/api/jobs/job1":
            return httpx.Response(
                200, json={"status": "failed", "error": "Mustang crashed"}
            )
        raise AssertionError(f"unexpected path {request.url.path}")

    _install_mock_transport(monkeypatch, handler)

    parser = cli.build_parser()
    args = parser.parse_args(
        ["align", "4HHB", "2HHB", "--wait", "--poll-interval", "0"]
    )
    exit_code = args.func(args)

    assert exit_code == 1
    assert "Mustang crashed" in capsys.readouterr().err


def test_status_command_prints_the_job_payload(monkeypatch, capsys):
    def handler(request):
        assert request.url.path == "/api/jobs/job1"
        return httpx.Response(200, json={"status": "completed", "run_id": "run_abc"})

    _install_mock_transport(monkeypatch, handler)

    parser = cli.build_parser()
    args = parser.parse_args(["status", "job1"])
    exit_code = args.func(args)

    assert exit_code == 0
    assert "run_abc" in capsys.readouterr().out


def test_status_command_reports_unknown_job(monkeypatch, capsys):
    def handler(request):
        return httpx.Response(404, json={"detail": "not found"})

    _install_mock_transport(monkeypatch, handler)

    parser = cli.build_parser()
    args = parser.parse_args(["status", "nope"])
    exit_code = args.func(args)

    assert exit_code == 1
    assert "No job found" in capsys.readouterr().err


def test_report_command_downloads_the_pdf(monkeypatch, tmp_path, capsys):
    def handler(request):
        assert request.url.path == "/api/report"
        assert request.url.params["run_id"] == "run_abc"
        return httpx.Response(200, content=b"%PDF-1.4 mock report")

    _install_mock_transport(monkeypatch, handler)

    output_path = tmp_path / "out.pdf"
    parser = cli.build_parser()
    args = parser.parse_args(["report", "run_abc", "--output", str(output_path)])
    exit_code = args.func(args)

    assert exit_code == 0
    assert output_path.read_bytes() == b"%PDF-1.4 mock report"


def test_report_command_surfaces_a_backend_error(monkeypatch, tmp_path, capsys):
    def handler(request):
        return httpx.Response(404, text="Run not found")

    _install_mock_transport(monkeypatch, handler)

    output_path = tmp_path / "out.pdf"
    parser = cli.build_parser()
    args = parser.parse_args(["report", "run_abc", "--output", str(output_path)])
    exit_code = args.func(args)

    assert exit_code == 1
    assert not output_path.exists()


def test_api_key_is_sent_as_the_x_api_key_header(monkeypatch):
    def handler(request):
        assert request.headers.get("X-API-Key") == "secret123"
        return httpx.Response(202, json={"job_id": "job1", "status": "queued"})

    _install_mock_transport(monkeypatch, handler)

    parser = cli.build_parser()
    args = parser.parse_args(["--api-key", "secret123", "align", "4HHB", "2HHB"])
    exit_code = args.func(args)

    assert exit_code == 0


def test_poll_job_times_out_if_never_completed(monkeypatch, capsys):
    monkeypatch.setattr(cli, "DEFAULT_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)

    def handler(request):
        return httpx.Response(200, json={"status": "running"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(base_url="http://mock", transport=transport) as client:
        run_id = cli._poll_job(client, None, "job1", 0)

    assert run_id is None
    assert "Timed out" in capsys.readouterr().err
