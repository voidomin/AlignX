"""Concurrency/load tests for the job submission + polling machinery in
src/backend/api.py. alignment_jobs/discovery_jobs/_job_submission_timestamps
are plain process-local dicts (see docs/deployment/DEPLOYMENT.md's "Known
limitations" note) - these tests exist to empirically verify what that
design is and isn't safe for within a single process, rather than assuming
either way. Real concurrency, not just sequential TestClient calls: uses
httpx.AsyncClient + ASGITransport so requests genuinely overlap on the
event loop, same as they would under real concurrent traffic."""

import asyncio
import time
from unittest.mock import patch

import httpx
import pytest

import src.backend.api as api_module
from src.backend.api import app


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def _drain_background_tasks():
    """Waits for the fire-and-forget asyncio.create_task() jobs an endpoint
    scheduled (e.g. _execute_discovery_job) to actually finish before the
    test returns - otherwise they can still be mid-flight when pytest tears
    down this test's event loop, which shows up as pytest-asyncio being
    mysteriously slow across the whole file rather than a clean failure."""
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    if pending:
        await asyncio.wait(pending, timeout=5)


@pytest.mark.asyncio
async def test_rate_limiter_holds_exactly_at_the_limit_under_concurrent_bursts():
    """rate_limit_job_submissions' check-then-append has no `await` between
    reading and writing _job_submission_timestamps, so it can't lose count
    to interleaving even under real concurrency (asyncio only switches
    coroutines at await points) - verify that holds under an actual
    concurrent burst, not just sequential requests."""
    api_module.discovery_jobs.clear()
    api_module._job_submission_timestamps.clear()
    with patch.object(api_module, "_DISCOVERY_RATE_LIMIT_MAX", 3), patch(
        "src.backend.discovery_coordinator.DiscoveryCoordinator.run_discovery_pipeline"
    ) as mock_run:
        mock_run.return_value = (True, "ok", {"pdb_id": "4RLT"})
        async with _client() as client:
            responses = await asyncio.gather(
                *(
                    client.post("/api/jobs/discover", json={"pdb_id": "4RLT"})
                    for _ in range(10)
                )
            )
        await _drain_background_tasks()

    statuses = [r.status_code for r in responses]
    assert statuses.count(202) == 3
    assert statuses.count(429) == 7

    api_module.discovery_jobs.clear()
    api_module._job_submission_timestamps.clear()


@pytest.mark.asyncio
async def test_concurrent_submissions_from_different_clients_are_rate_limited_independently():
    """Two distinct API keys must each get their own rate-limit bucket
    (_rate_limit_client_key partitions by key/IP) - a burst from one client
    must not consume another client's quota, even when both bursts overlap
    on the event loop at the same time."""
    api_module.discovery_jobs.clear()
    api_module._job_submission_timestamps.clear()
    with patch.object(api_module, "_DISCOVERY_RATE_LIMIT_MAX", 2), patch(
        "src.backend.discovery_coordinator.DiscoveryCoordinator.run_discovery_pipeline"
    ) as mock_run:
        mock_run.return_value = (True, "ok", {"pdb_id": "4RLT"})
        async with _client() as client:
            responses = await asyncio.gather(
                *(
                    client.post(
                        "/api/jobs/discover?api_key=client-a",
                        json={"pdb_id": "4RLT"},
                    )
                    for _ in range(4)
                ),
                *(
                    client.post(
                        "/api/jobs/discover?api_key=client-b",
                        json={"pdb_id": "4RLT"},
                    )
                    for _ in range(4)
                ),
            )
        await _drain_background_tasks()

    statuses = [r.status_code for r in responses]
    assert statuses.count(202) == 4  # 2 per client, not 2 total
    assert statuses.count(429) == 4

    api_module.discovery_jobs.clear()
    api_module._job_submission_timestamps.clear()


@pytest.mark.asyncio
async def test_many_concurrent_discovery_jobs_stay_individually_correct():
    """Submits several discovery jobs concurrently (each backed by a mock
    pipeline call that actually overlaps in wall-clock time, via a small
    sleep, to prove real concurrency rather than accidental serialization),
    then polls every job_id and confirms each one's result corresponds to
    its OWN pdb_id - a job dict entry getting clobbered by a concurrent
    sibling would show up here as cross-contaminated results."""
    api_module.discovery_jobs.clear()
    api_module._job_submission_timestamps.clear()
    pdb_ids = ["1CRN", "4RLT", "3UG9", "1L2Y", "2LYZ"]

    def fake_pipeline(*, pdb_id, databases=None, **_ignored):
        time.sleep(0.05)  # forces overlap with sibling to_thread calls
        return True, "ok", {"pdb_id": pdb_id, "hit_count": len(pdb_id)}

    with patch.object(api_module, "_DISCOVERY_RATE_LIMIT_MAX", len(pdb_ids)), patch(
        "src.backend.discovery_coordinator.DiscoveryCoordinator.run_discovery_pipeline",
        side_effect=fake_pipeline,
    ):
        async with _client() as client:
            submit_responses = await asyncio.gather(
                *(
                    client.post("/api/jobs/discover", json={"pdb_id": pid})
                    for pid in pdb_ids
                )
            )
            job_ids = [r.json()["job_id"] for r in submit_responses]

            for _ in range(20):
                if all(
                    api_module.discovery_jobs.get(jid, {}).get("status") == "completed"
                    for jid in job_ids
                ):
                    break
                await asyncio.sleep(0.02)

            poll_responses = await asyncio.gather(
                *(client.get(f"/api/jobs/{jid}") for jid in job_ids)
            )

    for pid, resp in zip(pdb_ids, poll_responses):
        body = resp.json()
        assert body["status"] == "completed"
        assert body["results"]["pdb_id"] == pid
        assert body["results"]["hit_count"] == len(pid)

    api_module.discovery_jobs.clear()
    api_module._job_submission_timestamps.clear()
