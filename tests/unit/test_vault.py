"""
Unit tests for `vault.py`.

Test structure:

UNIT TESTS
0. Fixtures & Setup
1. Constructor & Initialization
2. Accessors (Getters / Setters)
3. Main Methods
4. Fundamental Behavior & Mathematical Properties
5. Special Cases & Tolerance
6. Regression & Non-Regression
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orsync.vault import resolve_wikilinks_in_file, scan_vault, vault_tree

# ============================================================
# 0. FIXTURES & SETUP
# ============================================================


@pytest.fixture
def simple_vault(tmp_path: Path) -> Path:
    """Vault with a flat structure of three .md files."""
    (tmp_path / "NoteA.md").write_text("# Note A\nContent of A.", encoding="utf-8")
    (tmp_path / "NoteB.md").write_text("# Note B\nSee [[NoteA]].", encoding="utf-8")
    (tmp_path / "NoteC.md").write_text("# Note C\nNo links here.", encoding="utf-8")
    return tmp_path


@pytest.fixture
def nested_vault(tmp_path: Path) -> Path:
    """Vault with a nested folder structure."""
    (tmp_path / "folder").mkdir()
    (tmp_path / "NoteRoot.md").write_text("Root note.", encoding="utf-8")
    (tmp_path / "folder" / "NoteNested.md").write_text("Nested note.", encoding="utf-8")
    (tmp_path / "folder" / "NoteWithLink.md").write_text("See [[NoteRoot]].", encoding="utf-8")
    return tmp_path


@pytest.fixture
def vault_with_alias(tmp_path: Path) -> Path:
    """Vault with a wikilink using the [[Target|Alias]] syntax."""
    (tmp_path / "Target.md").write_text("Target content.", encoding="utf-8")
    (tmp_path / "Source.md").write_text("See [[Target|my alias]].", encoding="utf-8")
    return tmp_path


# ============================================================
# 1. CONSTRUCTOR & INITIALIZATION
# ============================================================


def test_scan_vault_raises_if_path_does_not_exist(tmp_path: Path):
    """scan_vault must raise ValueError when the path does not exist."""
    with pytest.raises(ValueError, match="does not exist"):
        scan_vault(tmp_path / "ghost")


def test_scan_vault_raises_if_path_is_not_a_directory(tmp_path: Path):
    """scan_vault must raise ValueError when the path is a file, not a directory."""
    file = tmp_path / "note.md"
    file.write_text("content", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory"):
        scan_vault(file)


def test_resolve_wikilinks_raises_if_file_does_not_exist(tmp_path: Path):
    """resolve_wikilinks_in_file must raise FileNotFoundError when md_path does not exist."""
    with pytest.raises(FileNotFoundError):
        resolve_wikilinks_in_file(tmp_path / "ghost.md", tmp_path)


# ============================================================
# 2. ACCESSORS (GETTERS / SETTERS)
# ============================================================


def test_scan_vault_returns_absolute_sorted_paths(simple_vault: Path):
    """scan_vault must return absolute paths in alphabetical order."""
    result = scan_vault(simple_vault)
    assert all(p.is_absolute() for p in result)
    assert result == sorted(result)


def test_scan_vault_excludes_non_md_files(tmp_path: Path):
    """scan_vault must ignore files that are not .md."""
    (tmp_path / "note.md").write_text("md file", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"")
    (tmp_path / "data.csv").write_text("a,b", encoding="utf-8")
    result = scan_vault(tmp_path)
    assert len(result) == 1


def test_scan_vault_empty_vault_returns_empty_list(tmp_path: Path):
    """scan_vault must return an empty list when the vault has no .md files."""
    assert scan_vault(tmp_path) == []


# ============================================================
# 3. MAIN METHODS
# ============================================================


def test_scan_vault_discovers_nested_files(nested_vault: Path):
    """scan_vault must find .md files in subdirectories."""
    result = scan_vault(nested_vault)
    assert len(result) == 3


def test_resolve_wikilinks_resolves_known_link(simple_vault: Path):
    """[[NoteA]] must be replaced with a relative Markdown link."""
    result = resolve_wikilinks_in_file(simple_vault / "NoteB.md", simple_vault)
    assert "[[NoteA]]" not in result
    assert "[NoteA]" in result


def test_resolve_wikilinks_unknown_link_becomes_plain_text(tmp_path: Path):
    """An unresolved [[link]] must be replaced with plain text (label only)."""
    (tmp_path / "Source.md").write_text("See [[GhostNote]].", encoding="utf-8")
    result = resolve_wikilinks_in_file(tmp_path / "Source.md", tmp_path)
    assert "[[GhostNote]]" not in result
    assert "GhostNote" in result


def test_resolve_wikilinks_alias_syntax_uses_alias_as_label(vault_with_alias: Path):
    """[[Target|Alias]] must produce [Alias](...) with the alias as link label."""
    result = resolve_wikilinks_in_file(vault_with_alias / "Source.md", vault_with_alias)
    assert "my alias" in result
    assert "[[Target|my alias]]" not in result


def test_resolve_wikilinks_nested_target_resolved(nested_vault: Path):
    """A wikilink to a file in a subdirectory must resolve correctly."""
    result = resolve_wikilinks_in_file(nested_vault / "folder" / "NoteWithLink.md", nested_vault)
    assert "[[NoteRoot]]" not in result
    assert "[NoteRoot]" in result


def test_resolve_wikilinks_duplicate_stem_becomes_plain_text(tmp_path: Path):
    """A [[link]] targeting a stem that exists in two folders must become plain text."""
    (tmp_path / "folder1").mkdir()
    (tmp_path / "folder2").mkdir()
    (tmp_path / "folder1" / "Note.md").write_text("Content 1.", encoding="utf-8")
    (tmp_path / "folder2" / "Note.md").write_text("Content 2.", encoding="utf-8")
    (tmp_path / "Source.md").write_text("See [[Note]].", encoding="utf-8")
    result = resolve_wikilinks_in_file(tmp_path / "Source.md", tmp_path)
    assert "[[Note]]" not in result
    assert "Note" in result
    assert "](folder" not in result


def test_vault_tree_output(simple_vault: Path):
    """vault_tree must return a non-empty string containing the vault name and all filenames."""
    result = vault_tree(simple_vault)
    assert isinstance(result, str)
    assert simple_vault.name in result
    for name in ["NoteA.md", "NoteB.md", "NoteC.md"]:
        assert name in result


def test_vault_tree_nested_vault(nested_vault: Path):
    """vault_tree must render all files in a nested vault structure."""
    result = vault_tree(nested_vault)
    assert "NoteRoot.md" in result
    assert "NoteNested.md" in result
    assert "folder" in result


# ============================================================
# 4. FUNDAMENTAL BEHAVIOR & MATHEMATICAL PROPERTIES
# ============================================================


def test_resolve_wikilinks_no_links_returns_unchanged_content(simple_vault: Path):
    """A file with no wikilinks must be returned unchanged."""
    note_c = simple_vault / "NoteC.md"
    original = note_c.read_text(encoding="utf-8")
    assert resolve_wikilinks_in_file(note_c, simple_vault) == original


def test_resolve_wikilinks_multiple_links_all_resolved(tmp_path: Path):
    """All [[wikilinks]] in a file must be resolved independently."""
    (tmp_path / "A.md").write_text("A", encoding="utf-8")
    (tmp_path / "B.md").write_text("B", encoding="utf-8")
    (tmp_path / "Source.md").write_text("[[A]] and [[B]].", encoding="utf-8")
    result = resolve_wikilinks_in_file(tmp_path / "Source.md", tmp_path)
    assert "[[A]]" not in result
    assert "[[B]]" not in result
    assert "[A]" in result
    assert "[B]" in result


# ============================================================
# 5. SPECIAL CASES & TOLERANCE
# ============================================================


def test_resolve_wikilinks_self_link_does_not_crash(tmp_path: Path):
    """A file linking to itself must not crash."""
    (tmp_path / "Self.md").write_text("See [[Self]].", encoding="utf-8")
    result = resolve_wikilinks_in_file(tmp_path / "Self.md", tmp_path)
    assert "[[Self]]" not in result


def test_resolve_wikilinks_link_with_spaces_in_name(tmp_path: Path):
    """Wikilinks with spaces in the target name must be handled."""
    (tmp_path / "My Note.md").write_text("Content.", encoding="utf-8")
    (tmp_path / "Source.md").write_text("See [[My Note]].", encoding="utf-8")
    result = resolve_wikilinks_in_file(tmp_path / "Source.md", tmp_path)
    assert "[[My Note]]" not in result


# ============================================================
# 6. REGRESSION & NON-REGRESSION
# ============================================================
# This section contains tests added after bug fixes.
# The goal is to ensure that previously identified issues never
# reappear in future changes.
#
# If no prior bugs or regressions have been identified,
# this section remains empty until needed.
# ============================================================
