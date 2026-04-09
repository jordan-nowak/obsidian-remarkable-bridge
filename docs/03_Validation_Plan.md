# Validation Plan

> This document defines the test strategy: what to test, with what inputs,
> against what reference, and according to what success criteria.
>
> Written in parallel with the Detailed Design, before any implementation.
> Updated whenever a functional requirement or hypothesis changes.

---

## Objectives

| Objective | Description |
|-----------|-------------|
| **Correctness** | Verify that each module produces the expected numerical results |
| **Robustness** | Verify that edge cases and invalid inputs are handled correctly |
| **Isolation** | Verify that each module is testable without a physical device |
| **Annotation safety** | A PDF annotated on the reMarkable is never overwritten - the VERSION decision is always triggered when annotations are detected |

---

## Reference Problem

> The main reference case used to validate the full pipeline.
> Must be simple and analytically known (or from a trusted source).

| Parameter | Symbol | Value | Unit |
|-----------|--------|-------|------|
| [Ex : Applied load] | P | [value] | N |
| [Ex : Length] | L | [value] | m |

**Reference source:** [Analytical formula / standard / known benchmark]

---

## Test Strategy

### Unit Tests

> Tests per module, in isolation. All SSH calls, subprocess calls and filesystem side effects are mocked. No physical device required. 
> 
> 6-category structure applied systematically:
> 0. Fixtures & Setup
> 1. Constructor & Initialization
> 2. Accessors (Getters / Setters)
> 3. Main Methods
> 4. Fundamental Behavior & Mathematical Properties
> 5. Special Cases & Tolerance
> 6. Regression & Non-Regression

#### Module : `setup_check.py`

`setup_check.py` verifies that the local environment is ready before the pipeline is launched: OS detected, Pandoc accessible, SSH connection to the tablet established, firmware version readable. Each check is independent-a failure in one does not block another.

**Test Assumptions**
- All SSH and subprocess calls are mocked - no physical device required.
- SSH scenarios cover: USB success, WiFi success, USB failure with WiFi fallback, total failure, timeout, missing key, authentication error.
- Pandoc scenarios cover: found, missing from PATH, non-zero return code, timeout.

**Success Criteria**
- `run_check` always returns a `CheckReport` (never raises an exception).
- `CheckReport.all_ok` is `False` as soon as a single item fails.
- The firmware is read via USB by default, via WiFi as a fallback, marked `skipped` if both fail.
- The WiFi check is marked `skipped` (status `True`) when no WiFi IP is configured.
- `run_check` returns exactly 5 items, with or without WiFi configured.

#### Module : `vault.py`

`vault.py` handles the interaction with an Obsidian vault. It is responsible for discovering Markdown files, resolving Obsidian-style `[[wikilinks]]`, and exposing a simplified representation of the vault structure.

**Test Assumptions**
- Tests run on temporary directories to simulate real vaults.
- No external dependencies are required.

**Success Criteria**
- The module correctly discovers all Markdown files in a vault.
- Wikilinks are properly converted into standard Markdown links when the target exists.
- Invalid or missing links are handled safely without breaking the content.
- Relative paths are correctly computed across directories.
- The vault structure is represented in a readable and deterministic way.

---

### Integration Tests

> Tests of the full pipeline - multiple modules interacting. SSH and subprocess remain mocked; the vault and sync state use real temporary files.
> 
> This is the 7e structure applied systematically:
> 7. Interface contract with downstream modules

#### [TODO] Module: `[module_name_1]`
<!-- Focus on the high-level goals (why, what, under what conditions) 
     without listing the tests one by one. -->

---

### Functional Tests

> Tests modules with real hardware, software and configuration.
> 
> Run manually with `pytest tests/functional/ --functional --no-cov -s`. Never run in CI.

#### Module : `setup_check.py`

Covers three hardware states: tablet connected (nominal), tablet disconnected (degraded), and tablet reconnected (recovery). Each state is a separate test file.

**Prerequisites:**
- USB connection
- SSH key deployed
- Pandoc installed

---

## Coverage Requirements

| Module           | Coverage threshold |
|------------------|--------------------|
| `setup_check.py` | ≥ 90%              |
| `vault.py`       | ≥ 90%              |
| `converter.py`   | ≥ 90%              |
| `sync_engine.py` | **100%**           |
| `remarkable.py`  | ≥ 90%              |
| `puller.py`      | ≥ 90%              |
| **Global**       | **≥ 90%**          |

Coverage is measured by `pytest-cov` and enforced in CI. Any PR below the threshold is blocked.

`sync_engine.py` is the only module that is 100% complete - this module determines whether to overwrite, skip, or version the notes stored on the tablet to prevent accidentally overwriting the user's annotations. Special attention is required for this module to ensure that no annotations are overwritten without warning.

---

[<-- Detailed Design](./02_Detailed_Design.md) · [Roadmap -->](./Roadmap.md)