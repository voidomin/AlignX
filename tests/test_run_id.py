import re
from datetime import datetime

from src.utils.run_id import generate_run_id

_RUN_ID_FORMAT = re.compile(r"^[a-z]+_\d+_[0-9a-f]{16}$")


def test_generate_run_id_matches_expected_format():
    run_id = generate_run_id("run")
    assert _RUN_ID_FORMAT.match(run_id), run_id


def test_generate_run_id_is_a_safe_path_segment():
    # Must stay inside api.py's _safe_segment() charset (alnum/underscore/hyphen)
    run_id = generate_run_id("discover")
    assert re.match(r"^[A-Za-z0-9_-]+$", run_id)


def test_generate_run_id_differs_across_calls_at_the_same_timestamp():
    same_instant = datetime(2026, 1, 1, 12, 0, 0)
    ids = {generate_run_id("run", same_instant) for _ in range(20)}
    # 20 calls at the identical second must not collide - this is exactly
    # the enumeration gap the random suffix exists to close (a bare
    # timestamp collides every time; the random suffix essentially never does).
    assert len(ids) == 20


def test_generate_run_id_keeps_the_prefix_and_timestamp_readable():
    now = datetime(2026, 3, 5, 9, 30, 0)
    run_id = generate_run_id("discover", now)
    assert run_id.startswith(f"discover_{int(now.timestamp())}_")
