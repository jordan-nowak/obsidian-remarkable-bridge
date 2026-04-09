"""
Obsidian vault scanner with basic wikilink resolution.

Scans a vault directory recursively for Markdown files and resolves
[[wikilink]] syntax to relative file paths for use by the converter.

Conventions:
- All paths are returned as absolute Path objects.
- The vault_path must exist and be a directory else if ValueError.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# ============================================================
# INTERNAL HELPERS
# ============================================================


def _build_index(vault_path: Path) -> dict[str, Path]:
    """
    Build a name -> absolute path index for all .md files in the vault.

    Used to resolve [[wikilinks]] to their actual file path.

    Parameters
    ----------
    vault_path : Path
        Root directory of the Obsidian vault.

    Returns
    -------
    dict[str, Path]
        Mapping from stem (filename without extension) to absolute path.
        If two files share the same stem, the last one found wins.
    """
    index: dict[str, Path] = {}
    duplicates: set[str] = set()

    for md in vault_path.rglob("*.md"):
        stem = md.stem
        if stem in index:
            duplicates.add(stem)
        else:
            index[stem] = md

    for stem in duplicates:
        index.pop(stem)

    return index


def _resolve_wikilinks(content: str, index: dict[str, Path], source: Path) -> str:
    """
    Replace [[Note]] wikilinks with relative Markdown links.

    Only resolves links that exist in the vault index. Unresolved links
    are replaced with plain text (the link label only).

    Parameters
    ----------
    content : str
        Raw Markdown content of a file.
    index : dict[str, Path]
        Name -> path index built from the vault.
    source : Path
        Absolute path of the file being processed (used to compute relative paths).

    Returns
    -------
    str
        Content with [[wikilinks]] replaced.
    """

    def replace_link(match: re.Match) -> str:  # type: ignore[type-arg]
        raw = match.group(1)
        # Support [[Note|Alias]] syntax - use alias as label, Note as target
        parts = raw.split("|", 1)
        target_stem = parts[0].strip()
        label = parts[1].strip() if len(parts) == 2 else target_stem

        if target_stem in index:
            relative = Path(os.path.relpath(index[target_stem], source.parent))
            return f"[{label}]({relative})"
        return label

    return re.sub(r"\[\[([^\[\]]+)\]\]", replace_link, content)


def _render_tree(vault_path: Path, files: list[Path]) -> str:
    """
    Render a tree-style string representation of vault files.

    Parameters
    ----------
    vault_path : Path
        Root of the vault (used as tree root label).
    files : list[Path]
        Absolute paths of files to include in the tree.

    Returns
    -------
    str
        Multi-line string with │ ├── └── characters.
    """
    lines = [vault_path.name + "/"]
    seen_dirs: set[Path] = set()

    for f in sorted(files):
        rel = f.relative_to(vault_path)
        parts = rel.parts

        # Add intermediate folders
        for i in range(len(parts) - 1):
            dir_path = vault_path.joinpath(*parts[: i + 1])
            if dir_path not in seen_dirs:
                indent = "    " * i
                lines.append(f"{indent}└── {parts[i]}/")
                seen_dirs.add(dir_path)

        # Add the file
        indent = "    " * (len(parts) - 1)
        lines.append(f"{indent}└── {parts[-1]}")

    return "\n".join(lines)


# ============================================================
# PUBLIC API
# ============================================================


def scan_vault(vault_path: Path) -> list[Path]:
    """
    Return the list of all .md files found in the vault.

    Parameters
    ----------
    vault_path : Path
        Root directory of the Obsidian vault. Must exist and be a directory.

    Returns
    -------
    list[Path]
        Absolute paths of all .md files, sorted alphabetically.

    Raises
    ------
    ValueError
        If vault_path does not exist or is not a directory.
    """
    if not vault_path.exists():
        raise ValueError(f"Vault path does not exist: {vault_path}")
    if not vault_path.is_dir():
        raise ValueError(f"Vault path is not a directory: {vault_path}")

    return sorted(vault_path.rglob("*.md"))


def resolve_wikilinks_in_file(md_path: Path, vault_path: Path) -> str:
    """
    Read a Markdown file and return its content with wikilinks resolved.

    Parameters
    ----------
    md_path : Path
        Absolute path to the .md file to process.
    vault_path : Path
        Root directory of the vault (used to build the resolution index).

    Returns
    -------
    str
        File content with [[wikilinks]] replaced by relative Markdown links
        or plain text when the target is not found.

    Raises
    ------
    FileNotFoundError
        If md_path does not exist.
    ValueError
        If vault_path is invalid.
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    index = _build_index(vault_path)
    content = md_path.read_text(encoding="utf-8")
    return _resolve_wikilinks(content, index, md_path)


def vault_tree(vault_path: Path) -> str:
    """
    Return a tree-style string representation of the vault's .md files.

    Parameters
    ----------
    vault_path : Path
        Root directory of the Obsidian vault.

    Returns
    -------
    str
        Human-readable tree string.

    Raises
    ------
    ValueError
        If vault_path is invalid.
    """
    files = scan_vault(vault_path)
    return _render_tree(vault_path, files)
