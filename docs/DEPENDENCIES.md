# Dependency Files

StructScope's Python dependencies are hash-pinned (see `S8544` in
`CHANGELOG.md`'s 3.63.0/3.65.0 entries) to stop a compromised/repointed
package release from silently substituting itself in at install time, even
with correct version pinning. That requires a `pip-compile --generate-hashes`
lock file per install target, which is why there are 5 files instead of one
`requirements.txt`:

| File | Purpose | Installed by |
|---|---|---|
| `requirements.in` | Human-edited source of the app's own dependencies (loose `>=` constraints, or `==` where a version needs to be pinned exactly - see the comment above `pandas`/`numpy`/`scipy`/`matplotlib`/`contourpy`). Edit this, never `requirements.txt` directly. | - |
| `requirements.txt` | Generated lock file (`pip-compile --generate-hashes --allow-unsafe -o requirements.txt requirements.in`) - every package pinned to an exact version with SHA-256 hashes. | `Dockerfile`, CI's "Install dependencies" step |
| `requirements-ci.in` | Human-edited source for `pip-audit`, the CI-only vulnerability scanner. Kept separate from `requirements.in` since it's a dev tool, not a shipped dependency. | - |
| `requirements-ci.txt` | Generated lock file for `requirements-ci.in`, same `pip-compile` command. | CI's "Audit Python dependencies" step |
| `requirements-pip.txt` | Hand-written hash pin for `pip` itself (the CI/Dockerfile self-upgrade step, before any lock file can be installed). No dependency tree to resolve, so no `.in` source or `pip-compile` involved - hashes are pulled directly from `https://pypi.org/pypi/pip/json`. | CI's "Install dependencies" step (first line) |

## Regenerating a lock file

**Always regenerate inside a container matching the actual deploy target**
(`python:3.10-slim`, the `Dockerfile`'s base image and CI's configured Python
version) - resolving on a different Python version can pick packages with no
wheel for 3.10 at all (confirmed the hard way: an initial attempt on a local
Python 3.12 environment produced a `requirements.txt` with `contourpy==1.3.3`,
which has no `cp310` wheel, and failed to install under Docker).

```bash
# from the repo root, after editing requirements.in
docker run --rm -v "$(pwd):/work" -w /work python:3.10-slim bash -c \
  "pip install pip-tools --quiet && \
   pip-compile --allow-unsafe --generate-hashes -o requirements.txt requirements.in"
```

Same pattern for `requirements-ci.in` → `requirements-ci.txt`.

If `pip-compile` backtracks for a long time without converging, a top-level
package most likely resolved to a version with no `cp310` wheel and pip is
trying every older release one at a time. Pin that package to `==<version>`
in the `.in` file first (find the newest `cp310`-compatible release via
`https://pypi.org/pypi/<package>/json`), then re-run.

## Verifying a rebuilt lock file

```bash
docker build -t structscope-verify .
docker run --rm -p 18080:8000 structscope-verify &
curl http://localhost:18080/health
```

A successful `docker build` already proves `--require-hashes` accepted every
pinned hash; `/health` confirms the app actually starts with the new set of
resolved versions.
