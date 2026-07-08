## What changed and why

<!-- The "why" matters more than the "what" - the diff already shows what
changed. -->

## Verification

- [ ] `pytest tests/` passes
- [ ] `npm test` passes (if `web-frontend/` changed)
- [ ] `black --check .` and `ruff check .` are clean
- [ ] `config.yaml`'s `app.version` bumped and `CHANGELOG.md` updated (for
      user-facing changes)
- [ ] Dependency changes went through `requirements.in` +
      regenerated the lock file (see `docs/DEPENDENCIES.md`), not a direct
      edit to `requirements.txt`

## Related issues

Closes #
