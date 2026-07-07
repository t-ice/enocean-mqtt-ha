# Development & release runbook (GitHub Flow)

How work flows from an idea to a published release. We use **GitHub Flow**: `master` is always
releasable, all work happens on short-lived branches merged via pull request, and releases are cut
from `master` by tagging. There is **no `dev` branch** — see "When to graduate" at the end.

For local setup and the style rules see [`../CONTRIBUTING.md`](../CONTRIBUTING.md) and
[`../STYLEGUIDE.md`](../STYLEGUIDE.md); to add support for a new device see
[`adding-devices.md`](adding-devices.md). This page is about the *flow*.

## The one rule

**`master` is always green and always releasable.** Every commit on `master` has passed CI and is a
state you'd be willing to ship. Nothing half-finished lands on `master` — that's what branches are for.

## One-time setup (until there's a remote)

The repo currently has no git remote. Before GitHub Flow works you need one:

```bash
git remote add origin git@github.com:t-ice/enocean-mqtt-ha.git
git push -u origin master
git push origin v1.0.0            # if the tag isn't pushed yet
```

Recommended on GitHub afterwards: **protect `master`** (Settings → Branches) — require a PR and
require the CI checks to pass before merge.

## Daily loop

```bash
# 1. Start from an up-to-date master
git switch master && git pull

# 2. Branch (short-lived, one topic)
git switch -c feat/secure-teach-in

# 3. Work + commit in small steps (plain messages, no AI-attribution trailer)
#    imperative subject; body explains WHY. See CONTRIBUTING.md.

# 4. Run the same checks CI will run, before pushing
uv run ruff check .
uv run ruff format --check src/enocean2mqtt tests tools
uv run mypy
uv run pytest -q                                   # fast unit tier
uv run pytest --cov=src/enocean2mqtt --cov-report=term-missing   # keep ≥ 90%
# heavier tiers when the change warrants them:
#   uv run pytest -m integration        # podman: mosquitto + ser2net emulator + daemon
#   tools/test-build.sh                 # build + smoke the add-on image (amd64 + aarch64)

# 5. Push and open a PR against master
git push -u origin feat/secure-teach-in
# open the PR on GitHub; fill in .github/pull_request_template.md
```

Then: **CI must be green**, get the review, **squash-merge** into `master`, delete the branch. Keep
PRs small and single-purpose — that's what keeps `master` releasable and history readable.

### Branch names

`feat/…` new feature · `fix/…` bug fix · `docs/…` documentation · `chore/…` tooling/deps ·
`refactor/…` behaviour-preserving cleanup. Short-lived — merge or discard within days, not weeks.

## What CI enforces (must be green to merge)

| Job (`.github/workflows/`) | Checks |
|---|---|
| `ci.yml` → `lint-and-test` | `ruff check`, `ruff format --check`, `mypy`, `pytest --cov` (floor **90%**), Python 3.12 + 3.13 |
| `ci.yml` → `shell` | `shellcheck` (run.sh, pi/install.sh, tools/*.sh) + `bats` (tests/addon/) |
| `ci.yml` → `addon-lint` | `apparmor_parser`, `hadolint`, HA add-on linter |
| `ci.yml` → `addon-build` | native amd64 + aarch64 image build + `enocean2mqtt --help` smoke |
| `codeql.yml` | CodeQL (Python) on `master` + weekly |

## Cutting a release

A release is a deliberate act — `master` accumulates merged features, and you promote them to a
version when ready. `release.yml`'s guard **requires the tag to equal `addon/config.yaml`'s
`version`**, so the bump and the tag must agree.

1. **Bump + changelog on a branch** (e.g. `chore/release-1.1.0`):
   - Edit `addon/config.yaml` → `version: "1.1.0"` ([semver](https://semver.org): patch = fixes,
     minor = backward-compatible features, major = breaking).
   - Add a `## 1.1.0 — <summary>` section to `addon/CHANGELOG.md` (one entry per version).
   - PR → CI green → merge to `master`.
2. **Tag the merge commit** on `master` and push:
   ```bash
   git switch master && git pull
   git tag -a v1.1.0 -m "Release 1.1.0"
   git push origin v1.1.0
   ```
3. **Publish the GitHub Release** for `v1.1.0` (Releases → Draft new release → pick the tag →
   Publish). Publishing triggers `release.yml`:
   - `guard` verifies `v1.1.0` (minus `v`) == config `version` `1.1.0` — mismatched → the release
     fails, fix the version/tag and re-run.
   - `publish` builds native amd64 + aarch64 and pushes
     `ghcr.io/t-ice/{amd64,aarch64}-enocean-mqtt-ha:1.1.0` + `:latest` with a signed provenance
     attestation.

### First release only — make the GHCR packages public

New GHCR packages are **private by default**, so installs fail until you flip them once:
GitHub → profile → **Packages** → `amd64-enocean-mqtt-ha` **and** `aarch64-enocean-mqtt-ha` →
Package settings → **Change visibility → Public**. Then verify: add the repo to a test HA — the
install should **pull** the image, not build it locally.

> The live local-build add-on mounted at `/Volumes/addons/enocean_mqtt_ha` is intentionally kept
> **without** the `image:` key so it builds from vendored `src/`. Don't add `image:` there until the
> images are published (else HA's "Rebuild" tries to pull a non-existent image).

## Hotfixes

Same as any change in GitHub Flow: branch `fix/…` off `master`, fix + test, PR, merge, then cut a
**patch** release (steps above). No separate hotfix branch type is needed while `master` is the only
long-lived line.

## When to graduate to a `dev` branch

Stay on GitHub Flow while this is solo/local and you release straight off `master`. Introduce a
`dev`/`main` split (Git Flow) when either: (a) other people contribute and you want an integration
line that bakes features together before release, or (b) you want `master` to move only in clean
version steps while several features accumulate elsewhere.
