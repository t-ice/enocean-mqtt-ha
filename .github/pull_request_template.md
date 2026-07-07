<!-- Thanks for contributing! Keep this short. -->

## What & why

<!-- What does this change do, and why? Link any related issue (e.g. "Closes #123"). -->

## Type of change

- [ ] Bug fix
- [ ] New device / EEP support
- [ ] Feature
- [ ] Docs / packaging
- [ ] Refactor (no behaviour change)

## Checklist

- [ ] `ruff check .` and `ruff format --check` pass
- [ ] `uv run mypy` passes
- [ ] `uv run pytest -q` passes and coverage stays ≥ 90%
- [ ] Added/updated tests for the change
- [ ] Updated `addon/CHANGELOG.md` if user-visible
- [ ] Respected the ports-and-adapters layering (I/O behind an adapter; domain stays pure)
