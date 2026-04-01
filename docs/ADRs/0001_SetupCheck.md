---
date: 30-MAR-2026
ref: 0001
author: JNO
---

# [0001]_SetupCheck

## Context

The execution of this synchronization pipeline depends on several external prerequisites; if any of these are missing, it will result in silent errors or unhelpful error messages:

- **Pandoc** must be installed and accessible in the system PATH (Windows and Linux/macOS)
- **The reMarkable 2** must be reachable via SSH, either through USB (`root@10.11.99.1`)
- **The RSA SSH key** must be deployed on the tablet to enable a passwordless connection

Without explicit verification at startup, a user could run `--push` and receive an error without knowing which dependency is missing. This would negatively impact the user experience.

This module is therefore called automatically when any CLI command (`--push`, `--pull`, `--all`) is run, or explicitly via the `--check` flag

It has no dependencies on other modules in the pipeline. It runs upstream and can be tested in a completely isolated manner.

## Decision

Implement `setup_check.py` as a standalone module exposing a main function `run_check(config: dict) -> CheckReport` that checks each dependency independently and returns a structured report.

**Proposed Development:**

```python
@dataclass
class CheckItem:
    name: str
    status: bool       # True = OK, False = FAIL
    detail: str        # Message returned by the report

@dataclass
class CheckReport:
    items: list[CheckItem]

    @property
    def all_ok(self) -> bool: ...

    def print_report(self) -> None: ...

def run_check(config: dict) -> CheckReport: ...
```

**Check list:**

| # | Verification            | Expected output format                                    |
|---|-------------------------|-----------------------------------------------------------|
| 1 | OS                      | [SUCCESS ✅] OS detected: Windows 10                      |
| 2 | Pandoc (PATH + version) | [SUCCESS ✅] Pandoc found: pandoc 3.1.2                   |
| 3 | Connection SSH USB      | [SUCCESS ✅] SSH USB connection: root@10.11.99.1          |
| 4 | Connection SSH WiFi     | [SKIPPED ⏭️] SSH WiFi connection: IP address not provided |
| 5 | Firmware reMarkable     | [SUCCESS ✅] reMarkable firmware: Version 3.25.1.1        |

If an error is returned, the format will be `[ERROR   ❌]`.

**Interface choice:**

`run_check` accepts `config: dict` (already parsed from `config.yaml`) rather than a file path, to decouple the module from the configuration-reading logic and make testing easier.

## Implementation

Branch: `feature/0001_SetupCheck`

Commit: `[0001] feat(setup_check): implement installation verification`

Implementation file: `src/orsync/setup_check.py`

**Key technical choices:**

- SSH timeout set to 5 seconds (configurable) to prevent prolonged downtime if the tablet is powered off.
- Structured logging via `guidelines_Logging`: each check is logged at the DEBUG level, and the final report at the INFO level.

**Changes**
- Implementation of installation verification
- Addition of associated unit tests (no physical device required)
- Addition of associated functional tests with real hardware/software/configuration
- Update the associated documentation

## Related Tests

All unit tests are implemented in `tests/test_setup_check.py` and cover `setup_check.py` according to the following structure:

UNIT TESTS
0. Fixtures & Setup
1. Constructor & Initialization
2. Accessors (Getters / Setters)
3. Main Methods
4. Fundamental Behavior & Mathematical Properties
5. Special Cases & Tolerance
6. Regression & Non-Regression

**CI pipeline requirements:**
- Tests run on Ubuntu and Windows
- Compatible with Python 3.11, 3.12, 3.13
- Mocked SSH connections: no physical device required in CI
- No regression allowed

## Risks/Impacts

- **Pandoc not found on Windows** - a common error if Pandoc isn't in the system PATH after installation. The error message should explicitly point to the solution (add `pandoc` to the PATH).

[<-- 0000_InitializeProject -->](0000_InitializeProject.md) · [0002_VaultScanner -->](0002_VaultScanner.md)
