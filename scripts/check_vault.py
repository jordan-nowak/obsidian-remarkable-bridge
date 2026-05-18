"""
Functionality test for vault.py with a real Obsidian vault.

Reads vault_path from config.yaml, scans the vault, and prints
a summary and tree view to the terminal.

Usage:
    python scripts/check_vault.py

Expected output:
    - Total number of .md files found
    - Number of duplicate stems detected (wikilinks that would fall back to plain text)
    - Full tree view of the vault
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

from orsync.vault import scan_vault, vault_tree

# Read the configuration to get the vault path
config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
vault_path = Path(config["vault_path"])

# Scan the vault and print results
print("-" * 60)
print(f"Vault : {vault_path}")

files = scan_vault(vault_path)
print(f"Files found : {len(files)}")

# Detect duplicate stems (wikilinks that will fall back to plain text)
stems = Counter(f.stem for f in files)
duplicates = {stem: count for stem, count in stems.items() if count > 1}

if duplicates:
    print(f"Duplicate stems ({len(duplicates)}) - wikilinks to these will become plain text:")
    for stem, count in sorted(duplicates.items()):
        print(f"  [{count}x] {stem}")
else:
    print("Duplicate stems : none")

# Display the vault tree
print()
print(vault_tree(vault_path))
