# Security Policy

StructScope is a research/portfolio project, not a company with a formal
bug-bounty program - this document is a straightforward account of what's
actually been checked, what hasn't, and how to report a problem.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for a security problem.
Instead, email `akashkbhat4414@gmail.com` with:

- What you found and why it's a problem.
- Steps to reproduce (a minimal request/payload is ideal).
- Which deployment you tested against (local dev, Docker, Streamlit Cloud).

You should get an initial response within a few days. There's no fixed
disclosure timeline given this is a small, unfunded project, but real
reports will be fixed and credited here (with your permission) once a fix
ships.

## Supported Versions

Only the latest tagged release on `main` is supported. There is no
long-term-support branch - fixes land as new releases, not backports.

## What's Actually Been Checked

This list exists so a report doesn't just re-discover something already
known and already fixed - see git history / `CHANGELOG.md` for exact
commits.

- **API key auth** (`ALIGNX_API_KEY`) gates every `/api/*`, `/results/*`,
  and `/raw/*` route when set - checked via `X-API-Key` header or
  `?api_key=` query param (the latter exists so plain `<a href>` download
  links can authenticate). `/results` and `/raw` serve generated
  reports/notebooks and structure files directly off disk, and previously
  bypassed this check entirely (a real bug, fixed - see
  `tests/test_api.py::TestApiKeyAuth`). Leaving `ALIGNX_API_KEY` unset
  intentionally leaves everything open, for local development.
- **Path traversal**: every user-controlled value that reaches a
  filesystem path (`pdb_id`, `session_id`, `run_id`, etc.) is validated
  against `^[A-Za-z0-9_-]+$` (`src/backend/api.py`'s `_safe_segment()`)
  before use, blocking `..`, `/`, and `\`.
- **Command/subprocess injection**: `MustangRunner` and `FoldseekRunner`
  build subprocess commands as argument lists (never `shell=True`), and
  every argument that comes from user input has already passed the path
  validation above.
- **SQL injection**: `src/backend/database.py` uses parameterized queries
  (`?` placeholders) exclusively - no string-built SQL anywhere.
- **Dependency vulnerabilities**: CI (`.github/workflows/ci.yml`) runs
  `pip-audit` against `requirements.txt` and `npm audit --audit-level=high`
  against the frontend on every push/PR.
- **Docker image**: CI builds the actual production `Dockerfile` and
  smoke-tests `/health` on every push/PR - previously this was manual/ad
  hoc (see `CHANGELOG.md`'s earlier "Verified" entries).
- **Job-submission rate limiting**: `/api/jobs/align` and
  `/api/jobs/discover` are rate-limited per API key (or IP, if no key is
  set) to prevent a single caller from queueing unlimited Mustang/Foldseek
  runs. Verified under real concurrent load
  (`tests/test_concurrency.py`) - the limiter's check-then-append has no
  `await` in its critical section, so it can't lose count to interleaving
  even under genuine concurrency.

## Known Limitations (Not Bugs, But Worth Knowing)

- **No independent security audit or penetration test has ever been done.**
  Everything above is what the maintainer has personally checked, not a
  third-party review.
- **In-memory job/rate-limit state is single-process only.** Running
  multiple `uvicorn` workers or container replicas breaks job polling and
  per-client rate limiting - see `docs/deployment/DEPLOYMENT.md`'s "Known
  Limitation" note. Stick to one worker process until this is externalized.
- **CORS defaults to `*` with credentials allowed** (`ALIGNX_CORS_ORIGINS`
  unset). This is intentional for zero-config local development, but it
  means a production deployment that forgets to set
  `ALIGNX_CORS_ORIGINS` is shipping wide-open, credentialed CORS - there's
  no CI/deploy-time check that catches this omission today.
- **Read endpoints aren't rate-limited**, only job submission is. A client
  with a valid API key (or no key, if unset) can poll `/api/history`,
  `/api/stats`, etc. as fast as it wants.
- **Discover mode depends on several third-party APIs** (Foldseek, EBI,
  STRING, Reactome, GMGC) that this project doesn't control the security
  posture of - see `docs/deployment/DEPLOYMENT.md`'s Network Requirements
  section for the full list.
