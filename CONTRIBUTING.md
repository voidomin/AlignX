# Contributing to StructScope

Thanks for your interest in improving StructScope. This doc covers the
practical parts of contributing: environment setup, how changes are
verified, and the conventions this codebase actually follows.

## Getting set up

1. Follow the **Quick Start** section in [README.md](README.md) to install
   dependencies and get the app running locally.
2. Install the dev/test extras (already in `requirements.txt`): `pytest`,
   `pytest-asyncio`, `pytest-cov`, `black`, `ruff`.
3. For frontend work, see `web-frontend/README` (or run
   `scripts/build_frontend.ps1`) and `npm test` inside `web-frontend/`.
4. Optional but recommended: `pip install pre-commit && pre-commit install`
   runs ruff/black/ESLint on every commit, so formatting/lint issues surface
   before you push rather than in CI. `.pre-commit-config.yaml` pins the
   same ruff/black versions CI checks against.

## Branching

`main` is always deployable and should stay that way. Use short-lived
`feat/*`/`fix/*` branches, open a PR into `main`, and squash-merge once CI is
green - see `.github/workflows/ci.yml` for what runs. `streamlit-stable` is a
separate, long-lived branch for whatever's actually live on Streamlit Cloud
(see `docs/deployment/DEPLOYMENT.md`) - don't merge `main` into it wholesale.

## Before opening a PR

- **Tests pass.** `pytest tests/` for backend, `npm test` inside
  `web-frontend/` for the SPA frontend. Every PR should keep the suite green
  - see `docs/testing/VERIFICATION.md` for the full protocol (setup checks,
  scientific-metric checks, API smoke tests, UI flow).
- **Formatting and lint are clean.** `black --check .` and `ruff check .` for
  the backend, `npm run lint` inside `web-frontend/` for the SPA (all three
  run in CI and will block the PR otherwise).
- **New code has real tests, not just "it imports."** This project has been
  through several test-coverage passes specifically because untested code
  paths hid real bugs. If you're adding a Streamlit UI function, see
  `tests/test_sidebar.py` or `tests/test_analysis.py` for the
  `streamlit.testing.v1.AppTest` pattern already established here.
- **Dependency changes go through `requirements.in`, not `requirements.txt`
  directly.** See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) - the lock
  file is generated, not hand-edited, and must be regenerated inside a
  `python:3.10-slim` container to match the actual deploy target.
- **Bump `config.yaml`'s `app.version`** and add a `CHANGELOG.md` entry for
  any user-facing change, following the existing entries' format (what
  changed, why, what was verified).

## Code style notes specific to this repo

- No unnecessary comments - only document the *why* (a non-obvious
  constraint, a workaround, a subtle invariant), never the *what* the code
  already says.
- Don't refactor beyond the scope of what you're asked to change. Several
  past cleanup passes deliberately scoped Cognitive Complexity fixes to
  extraction only, preserving exact existing behavior rather than also
  "improving" logic along the way.
- Prefer fixing a root cause over adding a fallback/try-except around it,
  unless the failure is a genuine external dependency (network call,
  optional tool not installed) rather than a bug in this codebase.
- If a SonarCloud/linter finding looks wrong, verify it against the actual
  code before "fixing" it - `src/frontend/sidebar.py`'s documented `S7504`
  false positive is a real example of a finding that would introduce a bug
  if blindly applied.

## Reporting issues

Open a GitHub issue, or see [SECURITY.md](SECURITY.md) if it's a security
concern rather than a bug report.
