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
    # Step 1 - Collect all nodes (subfolders + files) whilst preserving the sorted order and deduplicating folders.
    nodes: list[Path] = []
    seen_dirs: set[Path] = set()

    for f in sorted(files):
        rel = f.relative_to(vault_path)
        for i in range(len(rel.parts) - 1):
            dir_path = vault_path.joinpath(*rel.parts[: i + 1])
            if dir_path not in seen_dirs:
                nodes.append(dir_path)
                seen_dirs.add(dir_path)
        nodes.append(f)

    # Step 2 - For each node, determine whether it is the last child of its parent. Result: dict node -> is_last (bool).
    is_last_map: dict[Path, bool] = {}
    for node in nodes:
        rel = node.relative_to(vault_path)
        depth = len(rel.parts) - 1
        siblings = [
            n
            for n in nodes
            if n.parent == node.parent and len(n.relative_to(vault_path).parts) == depth + 1
        ]
        is_last_map[node] = node == siblings[-1]

    # Step 3 - Calculate continuation prefixes │ by depth level.
    # For each node, a 'd' should be displayed │ if the ancestor at that level is not itself the last child of its parent (i.e. there are still other siblings further down the tree).
    def _prefix(node: Path) -> str:
        rel = node.relative_to(vault_path)
        depth = len(rel.parts) - 1
        parts: list[str] = []
        for d in range(depth):
            ancestor = vault_path.joinpath(*rel.parts[: d + 1])
            parts.append("    " if is_last_map.get(ancestor, True) else "│   ")
        connector = "└── " if is_last_map[node] else "├── "
        return "".join(parts) + connector

    # Final rendering
    lines = [vault_path.name + "/"]
    for node in nodes:
        rel = node.relative_to(vault_path)
        label = rel.parts[-1] + ("/" if node.is_dir() else "")
        lines.append(_prefix(node) + label)

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


def resolve_wikilinks_in_file(
    md_path: Path,
    vault_path: Path,
    *,
    index: dict[str, Path] | None = None,
) -> str:
    """
    Read a Markdown file and return its content with wikilinks resolved.

    Parameters
    ----------
    md_path : Path
        Absolute path to the .md file to process.
    vault_path : Path
        Root directory of the vault (used to build the resolution index
        when *index* is not provided).
    index : dict[str, Path] | None, optional
        Pre-built vault index mapping note stems to their absolute paths.
        Pass this when converting multiple files to avoid rebuilding the
        index on every call. Build it once with ``_build_index(vault_path)``
        and reuse across calls. Defaults to None (index rebuilt each call).

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

    resolved_index = index if index is not None else _build_index(vault_path)
    content = md_path.read_text(encoding="utf-8")
    return _resolve_wikilinks(content, resolved_index, md_path)


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
