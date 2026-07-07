# Style guide

The project enforces one consistent style across all its technologies through automated tooling —
there is nothing to memorize. Install the hooks once and every commit is checked:

```bash
uv sync --extra dev          # or: pip install -e ".[dev]"
pre-commit install           # run the checks automatically on git commit
pre-commit run --all-files   # check the whole tree on demand
```

The tool configuration in `pyproject.toml`, `.yamllint`, `.hadolint.yaml`, `.editorconfig` and
`.pre-commit-config.yaml` is the source of truth; this document explains the intent.

## Python

- **Formatter: `ruff format`** is authoritative for layout — never hand-format. 100-column lines,
  double quotes, trailing commas. Don't fight it; if a line is unavoidably long (a URL, a spec
  reference), that's fine, but prefer extracting a local variable over a `# noqa`.
- **Linter: `ruff check`** with `E, F, W, I, UP, B, C4, SIM, N, RUF` — pycodestyle, pyflakes, isort,
  pyupgrade, bugbear, comprehensions, simplify, naming and Ruff's own rules. Run `ruff check --fix`.
- **Types: `mypy`** over `src/` (config in `pyproject.toml`). New code should be typed; add hints
  when you touch a function. Public functions in the ports/adapters layers must be fully typed.
- **Docstrings** say *why*, not *what*; match the density of the surrounding module.
- **Imports**: standard library, third-party, first-party — isort (rule `I`) orders them; don't do it
  by hand.

### Domain naming exceptions

EnOcean/EEP terms are part of the specification's vocabulary and are kept verbatim even where they
break PEP 8 — renaming them would obscure the mapping to the spec:

- ESP3/EEP constant groups are `SCREAMING_CASE` enums (`RORG`, `RETURN_CODE`, `PACKET`,
  `COMMON_COMMAND_CODE`) — `N801` is ignored in `protocol/constants.py`.
- `dBm` is the signal-strength field name — `N815` is ignored in `protocol/packet.py`.
- EEP shortcut keys (`TMP`, `SP`, `RSSI`, …) are MQTT-visible string keys, not identifiers, so they
  are never renamed.
- Upper-case byte-array fixtures in the protocol conformance tests (`TEMPERATURE`,
  `MAGNETIC_SWITCH`) are idiomatic test data — `N806` is ignored under `tests/protocol/conformance/`.

Everything outside those scopes follows normal `snake_case` / `CapWords`.

### Comments in a foreign language / symbols

Comments and docstrings may use `→` and German umlauts (`ä/ö/ü`) — `RUF001–003` are disabled so these
aren't flagged as ambiguous characters.

## YAML (Home Assistant add-on)

`yamllint` (config: `.yamllint`) checks `addon/config.yaml`, `addon/build.yaml`, translations and CI.
Line length is a **warning** (HA `name`/`description` strings run long); indentation is 2 spaces,
document-start markers are optional, and HA's bare `true/false/auto` values are allowed.

## Dockerfile

`hadolint` (config: `.hadolint.yaml`) lints `addon/Dockerfile`. `BUILD_FROM` has no default tag
(the HA Supervisor injects it — `DL3006` ignored) and `apk add python3` tracks the pinned base
image's repository (`DL3018` ignored). Otherwise: pin what you can, keep layers lean, no `latest`.

## Shell

`shellcheck` lints `addon/run.sh` and `tools/*.sh`. Quote expansions, prefer `[[ ]]`, and check the
exit status of commands whose failure matters.

## Editor

`.editorconfig` sets UTF-8, LF endings, a final newline, no trailing whitespace, and per-type indent
(4 for Python/shell, 2 for YAML/JSON/TOML). Most editors apply it automatically.

## When a rule is genuinely wrong

Prefer fixing the code. If a rule is wrong for a specific, well-understood reason, add a **scoped**
suppression with a comment explaining *why* (`# noqa: RULE - reason`) or a `per-file-ignores` entry —
never a blanket disable. The large data files (`profiles/eep/*.py`, `mapping/eep/*.py`, `_catalog.py`)
are excluded from lint/format wholesale because they are big dict literals; edit them directly.
