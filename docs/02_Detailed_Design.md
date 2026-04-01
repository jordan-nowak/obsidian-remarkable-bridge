# Detailed Design

> This document describes the mathematical formulation and algorithmic details of each module.
> It is the bridge between the Technical Specification and the implementation.
>
> Updated in the same PR as any algorithm or formulation change.

---

## Overview

See: [Software Architecture - Overview](./01_Software_Architecture.md#overview)

---

## Notation & Conventions

**General Conventions**
- All paths are absolute `pathlib.Path` objects.
- Relative paths in Markdown links are relative to the source file, not to the root of the vault.
- `sync_state.json` is the single source of truth for the sync history.

---

## Modules

### Responsibilities

See: [Software Architecture - Module Responsibilities](./01_Software_Architecture.md#module-responsibilities)

### `setup_check.py` - Algorithm

run_check(config) -> CheckReport:
1. Detect the OS
2. Search for pandoc in the PATH
   - Found -> Check the pandoc version
     - returncode == 0 -> CheckItem True, version retrieved
     - returncode != 0 -> CheckItem False, version not retrieved
   - Not found -> CheckItem False, do not call subprocess + provide installation guidance
3. Attempt USB SSH connection
   - Success -> CheckItem True
   - Failure -> CheckItem False (no raise)
4. If ip_wifi is not empty: attempt WiFi SSH connection
   Otherwise: CheckItem True with detail "skipped"
5. If USB (or WiFi) succeeded: read the tablet's version
   - Success -> CheckItem True
   - Failure -> CheckItem False with detail "error"
   Otherwise: CheckItem False with detail "skipped - no SSH connection available"

Fundamental rule: no check interrupts the subsequent ones.
The caller checks report.all_ok to decide whether to abort the pipeline.

---

[<-- Software Architecture](./01_Software_Architecture.md) · [Validation Plan -->](./03_Validation_Plan.md)