---
date: 30-MAR-2026
ref: 0001
author: JNO
---

# [0001]_SetupCheck

## Context

The execution of this synchronization pipeline depends on several external
prerequisites; if any of these are missing, it will result in silent errors
or unhelpful error messages:

- **Pandoc** must be installed and accessible in the system PATH (Windows and Linux/macOS)
- **Typst** must be installed and accessible in the system PATH
- **The reMarkable 2** must be reachable via SSH, either through USB (`root@10.11.99.1`)
  or WiFi (optional, configured in `config.yaml`)
- **The RSA SSH key** must be deployed on the tablet to enable a passwordless connection

Without explicit verification at startup, a user could run `--push` and receive an
error without knowing which dependency is missing. This would negatively impact the
user experience.

This module is therefore called automatically when any CLI command (`--push`,
`--pull`, `--all`) is run, or explicitly via the `--check` flag.

It has no dependencies on other modules in the pipeline. It runs upstream and can
be tested in a completely isolated manner.

## Decision

Implement `setup_check.py` as a standalone module exposing a main function
`run_check(config: dict) -> CheckReport` that checks each dependency independently
and returns a structured report.

**Data structures:**

```python
@dataclass
class CheckItem:
    name: str
    status: bool    # True = OK, False = FAIL
    detail: str     # Message returned by the report

    def __str__(self) -> str: ...    # formats to "[SUCCESS ✅] name: detail"

@dataclass
class CheckReport:
    items: list[CheckItem]

    @property
    def all_ok(self) -> bool: ...    # True only if all items passed

    def __repr__(self) -> str: ...   # formatted multi-line report

def run_check(config: dict) -> CheckReport: ...
```

**Check list:**

| # | Verification            | Example output                                            |
|---|-------------------------|-----------------------------------------------------------|
| 1 | OS                      | `[SUCCESS ✅] OS detected: Windows 10`                   |
| 2 | Pandoc (PATH + version) | `[SUCCESS ✅] Pandoc: pandoc 3.7.0.2`                    |
| 3 | SSH USB connection      | `[SUCCESS ✅] SSH USB connection: connected to root@10.11.99.1` |
| 4 | SSH WiFi connection     | `[SKIPPED ⏭️] SSH WiFi connection: skipped - no WiFi IP configured` |
| 5 | reMarkable firmware     | `[SUCCESS ✅] reMarkable firmware: 3.25.1.1`             |
| 6 | Typst (PATH + version)  | `[SUCCESS ✅] Typst: typst 0.13.1`                       |

If an error is returned, the format will be `[ERROR   ❌] name: detail`.

**Interface choice:**

`run_check` accepts `config: dict` (already parsed from `config.yaml`) rather than
a file path, to decouple the module from the configuration-reading logic and make
testing easier.

## Implementation

Branch: `feature/0001_SetupCheck`

Commit: `[0001] feat(setup_check): implement installation verification`

Implementation file: `src/orsync/setup_check.py`

**Architecture - internal decomposition:**

The orchestration is split into three explicit layers:

| Function | Role |
|---|---|
| `_build_context(config)` | Extracts and normalises config values into a frozen `_CheckContext` dataclass |
| `_build_checklist(ctx)` | Constructs the ordered list of zero-argument check callables |
| `_execute(checks)` | Runs each callable sequentially and builds the `CheckReport` |
| `run_check(config)` | Public entry point - chains the three above |

**SSH / firmware dependency resolution:**

SSH checks (USB and WiFi) are executed eagerly during `_build_checklist`, not lazily during `_execute`. Their results are cached in closures and replayed when `_execute` calls the returned callables. This avoids opening two SSH connections to the same host and allows `firmware_ip` to be resolved before the checklist is returned. The firmware check reuses the first successful SSH connection (USB takes precedence over WiFi).

**Binary detection - `_check_binary`:**

A shared helper checks any CLI binary: `shutil.which` for PATH presence, then `subprocess.run` with `capture_output=True, timeout=5`. The first line of stdout is used as the version string. Covers both `check_pandoc()` and `check_typst()`.

**Key technical choices:**

- SSH timeout set to 5 seconds (configurable via `ssh_timeout` in config) to prevent prolonged downtime if the tablet is powered off.
- SSH sessions managed via `_open_ssh_session` context manager (paramiko) - `AutoAddPolicy` for host key, `look_for_keys=False` to avoid scanning the SSH agent.
- Each check in `_execute` is wrapped in `try/except Exception` - any unexpected error is converted into a failed `CheckItem` without interrupting subsequent checks.
- Structured logging: each check is logged at `DEBUG` level, the final report at `INFO` level.

**`pyproject.toml` dependency:**

```toml
[project.dependencies]
paramiko = ">=3.0"
```

**Changes delivered:**

- Implementation of installation verification
- Unit tests in `tests/unit/test_setup_check.py` (no physical device required)
- Functional tests with real hardware/software/configuration
- Updated documentation

## Related Tests

All unit tests are implemented in `tests/unit/test_setup_check.py` and cover `setup_check.py` according to the following structure:

```
UNIT TESTS
0. Fixtures & Setup
1. Constructor & Initialization   - CheckItem, CheckReport, _CheckContext
2. Accessors                      - all_ok, __repr__, __str__
3. Main Methods                   - _check_binary, _check_os, _check_ssh, _check_firmware
4. Fundamental Behavior           - check ordering, firmware dependency resolution
5. Special Cases & Tolerance      - missing WiFi IP, unreachable host, empty version output
6. Regression & Non-Regression

INTEGRATION TESTS
7. Interface contract             - run_check output consumed by CLI (all_ok gate)
```

**CI pipeline requirements:**

- Tests run on Ubuntu and Windows
- Compatible with Python 3.11, 3.12, 3.13
- SSH connections mocked via `unittest.mock` (paramiko) - no physical device required in CI
- No regression allowed

## Risks/Impacts

- **Pandoc not found on Windows** - a common error if Pandoc isn't in the system PATH after installation. The error message explicitly points to the install URL.
- **Typst not found** - same pattern; error message points to `https://typst.app`.
- **SSH WiFi check** - skipped cleanly if `remarkable_ip_wifi` is absent or empty in config, producing a `status=True` item with `"skipped"` detail so `all_ok` is not affected.
- **Firmware check dependency** - if both SSH checks fail, firmware check produces a `status=False` item with `"skipped - no SSH connection available"` rather than attempting a connection.

[<-- 0000_InitializeProject](0000_InitializeProject.md) · [0002_VaultScanner -->](0002_VaultScanner.md)