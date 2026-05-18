---
date: 03-APR-2026
ref: 0002
author: JNO
---

# [0002]_VaultScanner

## Context

The synchronization pipeline requires two things from the Obsidian vault:

1. **A list of all `.md` files** to be synchronized. The Obsidian vault may contain hundreds of notes spread across nested subfolders.
2. **"Clean" Markdown content** passed to Pandoc for PDF conversion. `[[NoteA]]` wikilinks are non-standard Obsidian syntax that Pandoc does not understand. If left as is, they appear verbatim in the PDF or cause conversion errors.

This module is the first step in sending files from the PC to the tablet. It operates solely on the PC's local file system.

## Decision

We will implement `vault.py` with the following exposed interface:

```python
def scan_vault(vault_path: Path) -> list[Path]: ...
def resolve_wikilinks_in_file(md_path: Path, vault_path: Path) -> str: ...
def vault_tree(vault_path: Path) -> str: ...
```

**Scan strategy:**
Recursive, alphabetical sort, returns absolute paths. No filtering currently applied to certain subfolders (can be added via `config.yaml` if necessary).

**Wiki link resolution strategy:**
Regular expressions to identify content between `[[` and `]]` (regex: `\[\[([^\[\]]+)\]\]`).

Two cases to handle:
- `[[Note]]` -> `[Note](relative/path/to/Note.md)` if the note exists in the index.
- `[[Note|Alias]]` -> `[Alias](relative/path/to/Note.md)` if the note exists.

Otherwise, display as plain text (label only, without brackets):
- If the note exists in the index but is not unique.
- If the note is not found, and therefore the link is unresolved

## Implementation

Branch: `feature/0002_VaultScanner`

Commit: `[0002] feat(vault): implement vault scanner and wikilink resolution`

Implementation file: `src/orsync/vault.py`

**Changes**
- Implementation of the vault scanner and wikilink resolution
- Addition of associated unit tests
- Addition of a functionality test (with real vault)
- Update the associated documentation

## Related Tests

All unit tests are implemented in `tests/unit/test_vault.py` and cover `vault.py`.

**Functionality Test:**
A script named `scripts/check_vault.py` has been written to validate the module on a real Obsidian vault before integrating it into the rest of the pipeline. It reads `vault_path` from `config.yaml`, runs `scan_vault` and `vault_tree`, and then displays a summary including the total number of files and any duplicate files detected (i.e., wiki links that would be converted to plain text). This script is not part of the test suite and is never run in CI. It serves as a preliminary check of the validity of the actual data before proceeding with further development.

**CI pipeline requirements:**
- Tests run on Ubuntu and Windows
- Compatible with Python 3.11, 3.12, 3.13
- No system dependencies, only standard library (`pathlib`, `re`)
- No regression allowed

## Risks/Impacts

- **Obsidian folders to exclude** - `.obsidian/` and `templates/` contain `.md` files that are not notes to be synced. This may generate unnecessary PDFs. Handle this via `config.yaml` (exclusion list).
- **Index reconstruction** - `_build_index()` is called on every `resolve_wikilinks_in_file()` invocation, which rescans the entire vault each time. For large vaults or batch conversions, consider caching the index at the call site.

[<-- 0001_SetupCheck](0001_SetupCheck.md) · [0003_MarkdownToPdfConversion -->](0003_MarkdownToPdfConversion.md)
