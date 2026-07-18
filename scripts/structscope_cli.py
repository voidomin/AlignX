"""
A minimal CLI for the most common CI workflow against a running StructScope
backend: submit an alignment job, poll it to completion, download the
resulting PDF report. Uses only stdlib argparse + httpx (already a project
dependency) - no new dependency, and deliberately not a generated OpenAPI
client (see docs/guides/API_CLIENT.md for that route, which is documented
rather than checked in since generated code needs constant regeneration as
routes change).

Examples:
    python scripts/structscope_cli.py align 4HHB 2HHB --wait --report out.pdf
    python scripts/structscope_cli.py status <job_id>
    python scripts/structscope_cli.py report <run_id> --output out.pdf
"""

import argparse
import sys
import time

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_POLL_INTERVAL_SECONDS = 3.0
DEFAULT_TIMEOUT_SECONDS = 600.0
# PDF report generation is a synchronous, CPU-bound route (matplotlib/
# weasyprint rendering on a cache miss) - confirmed live that it can take
# well over the httpx default of 5s / a naive 30s on a first request for a
# given run, so every request timeout here (not just the overall --wait
# deadline above) needs real headroom.
REQUEST_TIMEOUT_SECONDS = 120.0


def _headers(api_key):
    return {"X-API-Key": api_key} if api_key else {}


def cmd_align(args):
    with httpx.Client(
        base_url=args.base_url, timeout=REQUEST_TIMEOUT_SECONDS
    ) as client:
        response = client.post(
            "/api/jobs/align",
            headers=_headers(args.api_key),
            params={"session_id": args.session_id} if args.session_id else None,
            json={
                "pdb_ids": args.pdb_ids,
                "remove_water": not args.keep_water,
                "remove_heteroatoms": not args.keep_heteroatoms,
            },
        )
        response.raise_for_status()
        job = response.json()
        print(f"Submitted job {job['job_id']} (status: {job['status']})")

        if not args.wait:
            return 0

        run_id = _poll_job(client, args.api_key, job["job_id"], args.poll_interval)
        if run_id is None:
            return 1

        print(f"Alignment complete - run_id: {run_id}")
        if args.report:
            _download_report(client, args.api_key, run_id, args.report)
        return 0


def cmd_status(args):
    with httpx.Client(
        base_url=args.base_url, timeout=REQUEST_TIMEOUT_SECONDS
    ) as client:
        response = client.get(
            f"/api/jobs/{args.job_id}", headers=_headers(args.api_key)
        )
        if response.status_code == 404:
            print(f"No job found with id {args.job_id}", file=sys.stderr)
            return 1
        response.raise_for_status()
        print(response.json())
        return 0


def cmd_report(args):
    with httpx.Client(
        base_url=args.base_url, timeout=REQUEST_TIMEOUT_SECONDS
    ) as client:
        return _download_report(client, args.api_key, args.run_id, args.output)


def _poll_job(client, api_key, job_id, poll_interval):
    """Blocks until the job reaches a terminal state, printing status
    transitions as they happen. Returns the completed run_id, or None if the
    job failed or the overall wait exceeded DEFAULT_TIMEOUT_SECONDS."""
    deadline = time.monotonic() + DEFAULT_TIMEOUT_SECONDS
    last_status = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}", headers=_headers(api_key))
        response.raise_for_status()
        job = response.json()
        status = job.get("status")
        if status != last_status:
            print(f"Job {job_id}: {status}")
            last_status = status

        if status == "completed":
            # The polling response nests the real run id under
            # results.id (confirmed against a live server - the
            # webhook payload gets a top-level run_id, but GET
            # /api/jobs/{job_id} does not).
            return (job.get("results") or {}).get("id")
        if status == "failed":
            print(f"Job failed: {job.get('error', 'unknown error')}", file=sys.stderr)
            return None

        time.sleep(poll_interval)

    print(f"Timed out waiting for job {job_id} to complete", file=sys.stderr)
    return None


def _download_report(client, api_key, run_id, output_path):
    response = client.get(
        "/api/report", params={"run_id": run_id}, headers=_headers(api_key)
    )
    if response.status_code != 200:
        print(
            f"Failed to fetch report for run {run_id}: {response.status_code} {response.text}",
            file=sys.stderr,
        )
        return 1
    with open(output_path, "wb") as f:
        f.write(response.content)
    print(f"Report saved to {output_path}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Minimal CLI for the StructScope REST API - submit/poll alignment jobs, download reports."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"StructScope backend base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Value for the X-API-Key header, if the backend has ALIGNX_API_KEY set",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    align_parser = subparsers.add_parser(
        "align", help="Submit a Mustang alignment job for 2+ PDB IDs/accessions"
    )
    align_parser.add_argument(
        "pdb_ids", nargs="+", help="2 or more PDB IDs or accessions to align"
    )
    align_parser.add_argument("--session-id", default=None)
    align_parser.add_argument(
        "--keep-water",
        action="store_true",
        help="Keep water molecules (HOH) instead of filtering them",
    )
    align_parser.add_argument(
        "--keep-heteroatoms",
        action="store_true",
        help="Keep non-ligand heteroatoms instead of excluding them",
    )
    align_parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll until the job completes or fails before exiting",
    )
    align_parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help=f"Seconds between polls when --wait is set (default: {DEFAULT_POLL_INTERVAL_SECONDS})",
    )
    align_parser.add_argument(
        "--report",
        default=None,
        help="With --wait: download the PDF report to this path once the job completes",
    )
    align_parser.set_defaults(func=cmd_align)

    status_parser = subparsers.add_parser("status", help="Poll a job's status once")
    status_parser.add_argument("job_id")
    status_parser.set_defaults(func=cmd_status)

    report_parser = subparsers.add_parser(
        "report", help="Download the PDF report for a completed run"
    )
    report_parser.add_argument("run_id")
    report_parser.add_argument("--output", required=True, help="Output PDF path")
    report_parser.set_defaults(func=cmd_report)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except httpx.HTTPStatusError as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 1
    except httpx.RequestError as e:
        print(f"Could not reach {args.base_url}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
