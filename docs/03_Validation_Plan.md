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

`setup_check.py` verifies that the local environment is ready before the pipeline is launched: OS detected, Pandoc accessible, SSH connection to the tablet established, firmware version readable, Typst accessible. Each check is independent — a failure in one does not block another.

**Test Assumptions**
- All SSH and subprocess calls are mocked - no physical device required.
- SSH scenarios cover: USB success, WiFi success, USB failure with WiFi fallback, total failure, timeout, missing key, authentication error.
- Pandoc scenarios cover: found, missing from PATH, non-zero return code, timeout.
- Typst scenarios cover: found, missing from PATH, non-zero return code, timeout.

**Success Criteria**
- `run_check` always returns a `CheckReport` (never raises an exception).
- `CheckReport.all_ok` is `False` as soon as a single item fails.
- The firmware is read via USB by default, via WiFi as a fallback, marked `skipped` if both fail.
- The WiFi check is marked `skipped` (status `True`) when no WiFi IP is configured.
- `run_check` returns exactly 6 items in all configurations (OS, Pandoc, SSH USB, SSH WiFi, firmware, Typst).
- `_execute` catches any unexpected exception from a check and records it as a failed `CheckItem`.

---

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
- A pre-built index passed via `index=` parameter produces the same result as building it internally.

---

#### Module : `converter.py`

`converter.py` converts `.md` files to PDF via a two-step pipeline: Pandoc + Typst.

Two modes are exposed through a **Strategy pattern**:
- **`raw`** (`RawStrategy`) — Pandoc + Typst without a template.
- **`eink`** (`TypstStrategy`) — Same pipeline with the bundled `eink.typ` Typst template, optimised for e-ink readability.

Both modes apply a Python preprocessing step before Pandoc: wikilink resolution, Obsidian callout conversion, emoji shortcode substitution, and spacing normalization.

A post-processing step (`_fix_typst_output`) patches `#horizontalrule` occurrences in the Pandoc-generated `.typ` file before Typst compilation.

**Test Assumptions**
- All `subprocess.run` calls are mocked — no Pandoc or Typst binary required in CI.
- `_fix_typst_output` is patched in most section 3 tests (it reads `doc.typ` from disk, which pandoc never creates when mocked).
- `emoji_json` scenarios cover: valid path (shortcodes substituted), `None` (no substitution), missing path (UserWarning emitted, non-fatal).
- Template scenarios cover: explicit path (used as-is), `None` (default resolved via `default_typst_template()`), missing path (`FileNotFoundError`).

**Success Criteria**

*Asset helpers:*
- `default_typst_template()` returns a `Path` pointing to `assets/eink.typ`.
- `default_emoji_json()` returns a `Path` pointing to `assets/emojis.json`.

*Preprocessors:*
- `_preprocess_wikilinks`: `[[Note]]` → `[Note](Note.md)`, `[[T|A]]` → `[A](T.md)`, `![[e]]` → textual marker, standard links untouched.
- `_preprocess_callouts`: all 10 known types produce their dedicated icon; unknown types use 📌; case-insensitive; standard blockquotes untouched.
- `_preprocess_spacing`: blank line inserted before list item after non-list line; no blank line between consecutive list items; `> ` separator inserted inside blockquote after bold header; rules skipped inside backtick and tilde code fences.
- `_preprocess_emojis`: known shortcodes replaced, unknown preserved, native Unicode untouched.
- `_preprocess`: full pipeline applied in correct order; tables, inline math, block math, and unrelated content preserved unchanged.

*`to_pdf_raw`:*
- Invokes `pandoc` first, then `typst compile`.
- Passes `-t typst` to Pandoc (not `--pdf-engine=lualatex`).
- Raises `FileNotFoundError` if `src` does not exist.
- Raises `RuntimeError` if Pandoc or Typst returns a non-zero exit code.
- Propagates `TimeoutExpired` from subprocess.
- Emits `UserWarning` (matching `"emojis.json"`) when the emoji JSON path does not exist — no exception.
- Creates `dst.parent` directory if it does not exist.
- Deletes a pre-existing `doc.typ` before invoking Pandoc.
- Accepts `verbose=True` without raising.

*`to_pdf_typst`:*
- Invokes `pandoc` with `-t typst` and `--template`, then `typst compile`.
- Raises `FileNotFoundError` if `src` does not exist.
- Raises `FileNotFoundError` (matching `"Template"`) if the Typst template does not exist.
- Uses `default_typst_template()` when `template=None`; does not call `default_typst_template()` when an explicit path is provided.
- Raises `RuntimeError` on Pandoc or Typst failure.
- Emits `UserWarning` when emoji JSON path is missing (non-fatal).
- Deletes pre-existing `dst` PDF and `doc.typ` before conversion.
- Creates `dst.parent` if it does not exist.

*Strategy pattern:*
- `make_strategy({})` defaults to `TypstStrategy`.
- `make_strategy({"pdf_mode": "raw"})` returns `RawStrategy`.
- `make_strategy({"pdf_mode": "latex"})` raises `ValueError` matching `"Unknown PDF mode"`.
- `RawStrategy.convert()` calls `to_pdf_raw` with correct arguments.
- `TypstStrategy.convert()` calls `to_pdf_typst` with correct arguments.

*Fundamental behavior:*
- Both modes produce identical preprocessed content from the same Obsidian source.
- `_fix_typst_output` replaces `#horizontalrule` and overwrites the file; no-op when absent.
- `_preprocess_spacing` correctly exits tilde (`~~~`) fences.

---

### Integration Tests

> Tests of the full pipeline - multiple modules interacting. SSH and subprocess remain mocked; the vault and sync state use real temporary files.
>
> This is the 7th section structure applied systematically:
> 7. Interface contract with downstream modules

#### Module: `converter.py`

**7. Contract with `setup_check` (conversion pipeline prerequisites)**

- `run_check` returning `all_ok=True` must be a necessary condition for a subsequent conversion call to succeed without raising a setup-related error.

---

### Functional Tests

> Tests modules with real hardware, software and configuration.
>
> Run manually with `pytest tests/functional/ --functional --no-cov -s`. Never run in CI.

#### Module : `setup_check.py`

Covers three hardware states: tablet connected (nominal), tablet disconnected (degraded), and tablet reconnected (recovery). Each state is a separate test.

**Prerequisites:**
- USB connection
- SSH key deployed
- Pandoc installed
- Typst installed

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

`sync_engine.py` is the only module that is 100% required — this module determines whether to overwrite, skip, or version the notes stored on the tablet to prevent accidentally overwriting the user's annotations. Special attention is required for this module to ensure that no annotations are overwritten without warning.

---

[<-- Detailed Design](./02_Detailed_Design.md) · [Roadmap -->](./Roadmap.md)