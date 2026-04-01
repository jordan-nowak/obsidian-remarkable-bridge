---
date: 28-MAR-2026
ref: 0000
author: JNO
---

# [0000]_InitializeProject

## Context

The `obsidian-remarkable-bridge` project is a personal tool developed in Python. The decisions made here will shape the structure of the repository.

**Constraints imposed from the outset**
- Python 3.11+ stack
- Windows compatibility is a priority (primary development environment)
- No reMarkable cloud - everything goes through local SSH
- Quality from the very first commit: linters and coverage configured

## Decision

**Project**
- `src/` directory structure using the `orsync` package. Prevents accidental imports from the root directory during testing.
- `pyproject.toml` with `setuptools>=68` – modern standard, no `setup.py`.
- `paramiko` (SSH), `pyyaml` (config). Minimal dependencies.

**Quality tools**
- Formatting: `black` (line-length=100)
- Lint: `ruff` (replaces flake8 + isort + pyupgrade)
- Tests: `pytest` + `pytest-cov`, global threshold ≥ 90%
- **CI** GitHub Actions, Ubuntu/Windows, Python 3.11/3.12/3.13.

**Sync status**
- `sync_state.json` in the project root, excluded from `.gitignore` (machine-specific).

**User configuration**
- `config.yaml` unversioned - `config.yaml.example` versioned as a reference.

## Implementation

Branch: `feature/0000_InitializeProject`

Commit: `[0000] feat(orsync): initialize project structure`

**Changes**
- Add initial README
- Add CI and coverage configuration (with CODECOV_TOKEN)
- Add GitHub PR Template
- Add Pytest, black and ruff configuration
- Add Pyproject configuration
- Add minimal pipeline test to validate src layout packaging
- First docs added with decision template

## Related Tests

No functional tests for this feature. Validation is structural:

- `py -m pip install -e .[dev]` completes without error
- `pytest` discovers and runs (1 tests collected is acceptable at this stage)
- CI pipeline passes on both Ubuntu and Windows across all three Python versions

## Risks/Impacts
- **`config.yaml`** - The user must configure this manually. Documented in the README.
- **Pandoc not included in `pyproject.toml`** - This is a system binary, not a pip package. Its presence will be checked by `setup_check.py`.
- **Impact on all downstream modules** - the `src/orsync/` layout and the `from orsync.xxx import yyy` import are the convention for the entire project. Any change to the layout would require updating all imports.

[<-- Roadmap](../Roadmap.md) · [0001_SetupCheck -->](./0001_SetupCheck.md)
