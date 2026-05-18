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
- XeLaTeX scenarios cover: found, missing from PATH, non-zero return code, timeout.
- WeasyPrint scenarios cover: found + render ok, not installed (ImportError), installed but native render raises (Cairo/Pango broken).
- Conditional mode scenarios cover: mode=raw (WeasyPrint skipped), mode=eink (XeLaTeX skipped), mode=both (both checked), mode absent from config (defaults to raw).

**Success Criteria**
- `run_check` always returns a `CheckReport` (never raises an exception).
- `CheckReport.all_ok` is `False` as soon as a single item fails.
- The firmware is read via USB by default, via WiFi as a fallback, marked `skipped` if both fail.
- The WiFi check is marked `skipped` (status `True`) when no WiFi IP is configured.
- `run_check` returns exactly 5 items, with or without WiFi configured.
- XeLaTeX check is included if and only if conversion_mode is `raw` or `both`.
- WeasyPrint check is included if and only if conversion_mode is `eink` or `both`.
- WeasyPrint check performs a minimal render, not just an import.
- `run_check` returns exactly 5 items when mode is `raw` or `eink`, and 6 items when mode is `both`.

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

#### Module : `converter.py`

`converter.py` converts `.md` files to PDF in two modes: `raw` (Pandoc + XeLaTeX, no stylesheet) and `eink` (Pandoc -> HTML -> WeasyPrint + CSS, emoji-capable, e-ink optimised).

The two modes are independent functions with distinct dependency profiles: `raw` requires only Pandoc; `eink` additionally requires WeasyPrint (optional dependency) and the bundled CSS and Noto Emoji font from `src/orsync/assets/`.

**Test Assumptions**
- All `subprocess.run` calls are mocked - no Pandoc binary required.
- `weasyprint` is mocked via `patch.dict("sys.modules")` - no WeasyPrint install required in CI.
- The temporary HTML file (eink pipeline) is simulated by writing it before calling `to_pdf_eink()` and asserting it is deleted after.
- CSS path scenarios cover: explicit path (used as-is), `None` (bundled default resolved via `_default_css()`), missing path (FileNotFoundError).

**Success Criteria**
- `check_pandoc()` raises `EnvironmentError` with install URL when Pandoc is absent from PATH.
- `to_pdf_raw()` raises `FileNotFoundError` when `md_path` does not exist.
- `to_pdf_raw()` passes `--pdf-engine=lualatex` to Pandoc.
- `to_pdf_raw()` raises `RuntimeError` on non-zero Pandoc exit; error message includes stderr.
- `to_pdf_raw()` raises `RuntimeError` on Pandoc timeout.
- `to_pdf_eink()` raises `FileNotFoundError` when `md_path` does not exist.
- `to_pdf_eink()` raises `FileNotFoundError` when the CSS path does not exist.
- `to_pdf_eink()` raises `ImportError` with `pip install` hint when WeasyPrint is not installed.
- `to_pdf_eink()` calls Pandoc with `-t html` before calling WeasyPrint.
- `to_pdf_eink()` passes the CSS file to WeasyPrint as a stylesheet.
- `to_pdf_eink()` deletes the temporary HTML file on both success and failure (finally block).
- `to_pdf_eink()` uses `_default_css()` when `css=None`; uses the explicit path without calling `_default_css()` when a path is provided.

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