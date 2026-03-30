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

#### [TODO] Module: `[module_name_1]`

| # | Test case - Description | Input | Expected result |
|---|-----------|-------|-----------------|
| UT-[MOD1]-01 | Normal case - [description] | [values] | [analytical value] |
| UT-[MOD1]-02 | Boundary - [description] | [boundary value] | [expected] |
| UT-[MOD1]-03 | Math property - [Ex: linearity] | [2×input] | [2×output] |
| UT-[MOD1]-04 | Physical property - [Ex: unit consistency] | [SI inputs] | [SI output] |
| UT-[MOD1]-05 | Input handling - scalar and array | `float`, `np.array` | same result |
| UT-[MOD1]-06 | Error - invalid input → exception | [invalid value] | `ValueError` |

---

### Integration Tests

> Tests of the full pipeline - multiple modules interacting. SSH and subprocess remain mocked; the vault and sync state use real temporary files.
> 
> This is the 7e structure applied systematically:
> 7. Interface contract with downstream modules

#### [TODO] Module: `[module_name_1]`

| #     | Test case - Description | Input   | Expected result |
|-------|-------------------------|---------|-----------------|
| IT-[MOD1]-01 | [Case] - [Description]  | [Input] | [Expected]      |

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