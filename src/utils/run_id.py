"""Run ID generation shared by Compare and Discover pipelines."""

import secrets
from datetime import datetime


def generate_run_id(prefix: str, now: datetime = None) -> str:
    """
    Build a run ID as "{prefix}_{unix_timestamp}_{random_suffix}".

    The random suffix is what makes a run ID safe to hand out or leave
    reachable by anyone who knows it - a bare timestamp is guessable/
    enumerable, and read endpoints like /api/report look a run up by
    run_id alone with no ownership check.
    """
    if now is None:
        now = datetime.now()
    return f"{prefix}_{int(now.timestamp())}_{secrets.token_hex(8)}"
