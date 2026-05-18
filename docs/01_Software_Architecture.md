# Software Architecture

> This document describes the overall structure of the project:
> module responsibilities, data flow, and design principles.
>
> Updated in the same PR as any module structure change or new external dependency.

---

## Overview

`obsidian-remarkable-bridge` is a Python package that implements a synchronization pipeline between an Obsidian vault (PC) and a reMarkable 2 tablet.

It supports two workflows:
- **PC -> rM (push)** 
	- Scan the Obsidian vault
    - Resolve wiki links
    - Convert `.md` files to PDF
    - Determine whether to sync (hash + annotations)
    - Upload via SSH with metadata

- **rM -> PC (pull)** 
	- Detection of annotated PDFs on the tablet
    - Transfer and archiving to `vault/remarkable/`

The pipeline is triggered manually via a CLI. It does not require a reMarkable cloud subscription; everything is done via SSH (USB).

---

## Package Structure

```tree
obsidian-remarkable-bridge/
├── src/
│   └── orsync/
│       ├── __init__.py
│       ├── setup_check.py    # Verification of hardware and software installation
│       ├── vault.py          # Scan the Obsidian vault and resolve wikilinks
│       ├── converter.py      # Convert .md to PDF using Pandoc + Typst
│       ├── sync_engine.py    # Decision logic: hash, annotations, versioning
│       ├── remarkable.py     # SSH connection, PDF upload, folder creation + metadata
│       ├── puller.py         # Pull of annotated notebooks from rM -> PC
│       └── assets/
│           ├── eink.typ      # Typst template for e-ink optimized PDF
│           └── emojis.json   # Emoji shortcode -> Unicode mapping
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_version.py
│   │   ├── test_setup_check.py
│   │   ├── test_vault.py
│   │   ├── test_converter.py
│   │   ├── test_sync_engine.py
│   │   ├── test_remarkable.py
│   │   └── test_puller.py
│   └── functional/
│       └── test_setup_check_real.py
│
├── scripts/
│   ├── check_converter.py    # Visual check of the converter pipeline
│   ├── check_vault.py        # Functional check on a real vault
│   ├── sync.py               # CLI: --push / --pull / --all / --check
│   └── samples/sample.md     # A simple markdown file
│
├── docs/
│   ├── ADRs/                 # One ADR per feature
│   ├── 01_Software_Architecture.md
│   ├── 02_Detailed_Design.md
│   ├── 03_Validation_Plan.md
│   ├── Roadmap.md
│   └── setup_ssh.md
│
├── sync_state.json           # Local state
├── config.yaml               # vault_path, remarkable_ip, target_folder
├── pyproject.toml
└── README.md
```

---

## Module Responsibilities

### `setup_check.py`
Verifies that the PC environment and the connection to the tablet are operational before any synchronization takes place.

Key inputs / outputs:
- **Input:** configuration (`config.yaml`)
- **Output:** `[SUCCESS ✅] / [ERROR ❌]` report for each dependency checked (OS, Pandoc, SSH USB, SSH WiFi, firmware, Typst)

### `vault.py`
Scans the Obsidian vault directory tree and resolves basic wikilinks into relative paths.

Key inputs / outputs:
- **Input:** `vault_path: Path` (from `config.yaml`)
- **Output:** `list[Path]` - absolute paths of all `.md` files in the vault

### `converter.py`
Converts `.md` files to PDF via a two-step pipeline: Pandoc + Typst.

Exposes two modes, both driven by a **Strategy pattern**:
- **`raw`** (`RawStrategy`) - Pandoc -> Typst -> PDF, without a template. Preprocessing applied.
- **`eink`** (`TypstStrategy`) - Same pipeline, using the bundled `assets/eink.typ` template, which optimises typography, heading colours, margins and page size for e-ink readability.

Both modes apply a Python preprocessing step before Pandoc:
wikilink resolution, Obsidian callout conversion, emoji shortcode substitution, and spacing normalization.

A post-processing step fixes `#horizontalrule` incompatibilities introduced by Pandoc before handing the `.typ` file to Typst.

Key inputs / outputs:
- **Input:** `src: Path`, `dst: Path`, optional `template`, `emoji_json`, `verbose`
- **Output:** `.pdf` file generated at `dst`
- **Strategy factory:** `make_strategy(config: dict) -> ConversionStrategy`

### `sync_engine.py`
Detects the presence of annotations on each note on the tablet and decides which action to take. To do this, an MD5 hash comparison is performed between the source and the stored state.

Key inputs / outputs:
- **Input:** `md_path: Path`, `sync_state.json`, tablet metadata
- **Output:** decision `SKIP | OVERWRITE | VERSION`, update of `sync_state.json`

### `remarkable.py`
Manages the SSH connection to the reMarkable and the upload of PDFs with their xochitl structure (`.metadata`, `.content`).

Key inputs / outputs:
- **Input:** `pdf_path: Path`, `uuid: str`, `parent_uuid: str`, `paramiko` SSH session
- **Output:** files uploaded to `xochitl/` on the tablet

### `puller.py`
Retrieves annotated notebooks from the tablet to the `remarkable/` folder on the vault PC.

Key inputs / outputs:
- **Input:** `paramiko` SSH session, `vault_path: Path`
- **Output:** `.pdf` files copied to `vault/remarkable/`, `sync_state.json` updated

---

## Data Flow

### From PC to reMarkable (`--push`)

```flow
1. config.yaml

2. setup_check  - checks OS, Pandoc, Typst, SSH, and tablet connection

3. vault        - lists .md files in the PC vault

4. sync_engine  - compares MD5 hashes with sync_state.json
                - queries Remarkable to detect annotations
	            - decides: SKIP / OVERWRITE / VERSION

5. converter    - .md -> .pdf (raw or eink mode via ConversionStrategy)

6. remarkable   - uploads .pdf + .metadata + .content via SSH
                - restarts the tablet

7. sync_engine  - updates sync_state.json
```

### From reMarkable to PC (`--pull`)

```flow
1. config.yaml

2. remarkable   - lists annotated notebooks

3. puller       - copies annotated .pdf files to vault/remarkable/

4. sync_engine  - updates sync_state.json
```

---

## Design Principles

- Modules are independently testable
- Scripts are separated from the library

- No global state - all dependencies are passed explicitly
- Explicit and persistent state - `sync_state.json` is the sole source of the current status
- Annotation protection is a priority
- Command-Line Interface (CLI) as the orchestrator
- No dependency on proprietary APIs
- No reMarkable cloud - everything goes through local SSH (USB)

---

## Dependencies

| Package      | Version | Role                                            |
| ------------ | ------- | ----------------------------------------------- |
| `paramiko`   | ≥ 3.0   | SSH connection and SCP transfer to reMarkable   |
| `pyyaml`     | ≥ 6.0   | Reading `config.yaml`                           |
| `pandoc`     | ≥ 3.1   | Markdown to Typst conversion (system binary)    |
| `typst`      | ≥ 0.11  | Typst source to PDF compilation (system binary) |
| `pytest`     | ≥ 7.0   | Testing framework                               |
| `pytest-cov` | ≥ 4.0   | Test coverage                                   |
| `black`      | ≥ 24.0  | Automatic formatting                            |
| `ruff`       | ≥ 0.3   | Static lint                                     |

> **Note:** `pandoc` and `typst` are system binaries, not pip packages. Their presence is verified at startup by `setup_check.py`.

---

[<-- Roadmap](./Roadmap.md) · [Detailed Design -->](./02_Detailed_Design.md)