"""
converter.py - Obsidian Markdown to PDF pipeline via Typst.

Three conversion modes:

    to_pdf_raw(src, dst)
        Raw conversion without a template: Pandoc -> Typst -> PDF.
        Preprocessing required to prevent Pandoc crashes.
        Pipeline:
          1. Python preprocessing (wikilinks, Obsidian callouts, emojis)
          2. Pandoc  Markdown -> .typ  (WITHOUT the eink.typ template)
          3. Typst   .typ -> PDF

    to_pdf_typst(src, dst)
        Full pipeline:
          1. Python preprocessing (wikilinks, Obsidian callouts, emojis)
          2. Pandoc  Markdown -> .typ  (WITH the eink.typ template)
          3. Typst   .typ -> PDF

System requirements:
    - pandoc  ≥ 3.1   in the PATH   (pandoc --list-output-formats | grep typst)
    - typst   ≥ 0.11  in the PATH   (https://typst.app or cargo install typst-cli)

Asset structure (next to this file):
    assets/
    ├── eink.typ        main Typst template
    └── emojis.json     name -> codepoint mapping  {"smile": "😄", ...}
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Protocol

FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
_LIST_ITEM_RE = re.compile(r"^(\s*[-*+]|\s*\d+\.)\s")

# ============================================================
# ASSET PATHS
# ============================================================


def _assets_dir() -> Path:
    """The "assets/" directory located next to this file."""
    return Path(__file__).parent / "assets"


def default_typst_template() -> Path:
    return _assets_dir() / "eink.typ"


def default_emoji_json() -> Path:
    return _assets_dir() / "emojis.json"


# ============================================================
# PREPROCESS MARKDOWN
# ============================================================


def _preprocess_wikilinks(text: str) -> str:
    """
    Converts Obsidian wikilinks into standard Markdown links.

    [[Note Title]]           -> [Note Title](Note Title.md)
    [[Note Title|Alias]]     -> [Alias](Note Title.md)
    ![[embed.md]]            -> (embed ignored - text marker)
    """
    # Embeds : ![[...]] -> text marker
    text = re.sub(
        r"!\[\[([^\]]+)\]\]",
        r"*(embed: \1)*",
        text,
    )
    # Wikilinks with alias : [[Target|Alias]]
    text = re.sub(
        r"\[\[([^\]|]+)\|([^\]]+)\]\]",
        lambda m: f"[{m.group(2)}]({m.group(1)}.md)",
        text,
    )
    # Simple wikilinks : [[Target]]
    text = re.sub(
        r"\[\[([^\]]+)\]\]",
        lambda m: f"[{m.group(1)}]({m.group(1)}.md)",
        text,
    )
    return text


def _preprocess_callouts(text: str) -> str:
    """
    Converts Obsidian callouts into rich Markdown blockquotes.

    > [!note] Title      -> > **📝 Note - Title**
    > [!warning] Title   -> > **⚠️ Warning - Title**
    > [!tip]             -> > **💡 Tip**
    """
    _icons: dict[str, str] = {
        "note": "📝",
        "info": "ℹ️",
        "tip": "💡",
        "warning": "⚠️",
        "danger": "🔥",
        "error": "❌",
        "success": "✅",
        "question": "❓",
        "quote": "💬",
        "abstract": "📋",
    }

    def _replace(m: re.Match) -> str:
        kind = m.group(1).lower()
        title = m.group(2).strip()
        icon = _icons.get(kind, "📌")
        label = kind.capitalize()
        if title:
            return f"> **{icon} {label} - {title}**"
        return f"> **{icon} {label}**"

    return re.sub(
        r"^> \[!(\w+)\][ \t]*(.*)?$",
        _replace,
        text,
        flags=re.MULTILINE,
    )


def _preprocess_spacing(text: str) -> str:
    """
    Ensures correct blank lines before list items and inside blockquotes.

    Two rules applied in a single line-by-line pass (code fences are skipped):

    1. List spacing
       A list item (- / * / + / 1.) not preceded by a blank line or another
       list item gets a blank line inserted before it.
       Prevents Pandoc from merging "label:\n- item" into a single paragraph.

    2. Blockquote body spacing
       Inside a blockquote, a bold header line ("> **…**") immediately followed
       by a content line ("> text") gets a "> " blank line inserted between them.
       Ensures Pandoc creates two distinct paragraphs within the quote block.
    """
    lines = text.splitlines()
    result: list[str] = []

    in_code_block = False
    fence_char: str | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # ── Track code fences (skip all rules inside) ──────────────────────
        m = FENCE_RE.match(stripped)
        if m:
            if not in_code_block:
                in_code_block = True
                fence_char = m.group(1)[0]
            elif stripped.startswith(fence_char * 3):
                in_code_block = False
                fence_char = None
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        # ── Rule 1 : blank line before a list item ──────────────────────────
        if _LIST_ITEM_RE.match(line):
            prev = result[-1] if result else ""
            prev_stripped = prev.strip()
            # Insert blank line if previous line is non-empty and not itself a list item
            if prev_stripped and not _LIST_ITEM_RE.match(prev):
                result.append("")

        # ── Rule 2 : blank separator inside blockquotes ─────────────────────
        # When a "> **bold header**" is immediately followed by "> body text",
        # insert a "> " blank line so Pandoc treats them as separate paragraphs.
        if (
            line.startswith("> ")
            and re.match(r"^> \*\*.+\*\*\s*$", line)
            and i + 1 < len(lines)
            and lines[i + 1].startswith("> ")
            and lines[i + 1].strip() != ">"
        ):
            result.append(line)
            result.append(">")
            continue

        result.append(line)

    return "\n".join(result)


def _preprocess_emojis(text: str, emoji_map: dict[str, str]) -> str:
    """
    Replaces :smile: shortcodes with the corresponding Unicode code points.

    Args:
        text:       Source Markdown text.
        emoji_map:  Name -> emoji dictionary, e.g. {"smile": "😄"}.

    Returns:
        Text with resolved shortcodes.
    """

    def _replace(m: re.Match) -> str:
        name = m.group(1)
        return emoji_map.get(name, m.group(0))  # conserve the original if unknown

    return re.sub(r":([a-zA-Z0-9_+-]+):", _replace, text)


def _preprocess(
    src: Path,
    *,
    emoji_json: Path | None = None,
) -> str:
    """
    Applies all preprocessing steps to an Obsidian Markdown file.

    Args:
        src:        Path to the source .md file.
        emoji_json: Path to emojis.json (None = no substitution).

    Returns:
        Preprocessed Markdown content, ready for Pandoc.
    """
    text = src.read_text(encoding="utf-8")
    text = _preprocess_callouts(text)
    text = _preprocess_spacing(text)
    text = _preprocess_wikilinks(text)
    if emoji_json is not None:
        mapping = json.loads(emoji_json.read_text(encoding="utf-8"))
        text = _preprocess_emojis(text, mapping)
    return text


def _prepare_conversion(
    src: Path,
    dst: Path,
    tmp: Path,
    emoji_json: Path | None,
) -> Path:
    """
    Setup shared across PDF conversion modes.

    Validates src, resolves the emoji path, creates the dst directory,
    pre-processes the Markdown and writes the intermediate file to tmp.

    Args:
        src:       Source Markdown file.
        dst:       Output PDF file (only its parent directory is created here).
        tmp:       Temporary directory already created by the caller.
        emoji_json: JSON emoji mapping. None -> default path.

    Returns:
        Path to the pre-processed Markdown file (tmp/preprocessed.md).

    Raises:
        FileNotFoundError: if src cannot be found.
    """
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    resolved_emoji = emoji_json if emoji_json is not None else default_emoji_json()
    emoji_path: Path | None = resolved_emoji if resolved_emoji.exists() else None
    if emoji_path is None:
        warnings.warn(
            f"emojis.json not found: {resolved_emoji} - shortcodes not substituted",
            UserWarning,
            stacklevel=3,
        )

    dst.parent.mkdir(parents=True, exist_ok=True)

    preprocessed_md = tmp / "preprocessed.md"
    content = _preprocess(src, emoji_json=emoji_path)
    preprocessed_md.write_text(content, encoding="utf-8")

    return preprocessed_md


# ============================================================
# TYPST POST-PROCESSING
# ============================================================

# Inline Typst replacement for #horizontalrule.
# Replace every occurrence with the equivalent inline Typst snippet before handing the file to `typst compile`.
_HRULE_TYPST = (
    "#{\n"
    "  v(0.6em)\n"
    '  line(length: 100%, stroke: 0.4pt + rgb("#999999"))\n'
    "  v(0.6em)\n"
    "}"
)


def _fix_typst_output(typ_path: Path) -> None:
    """
    Post-processes the .typ file produced by Pandoc to fix known compatibility
    issues with recent Typst versions.

    Currently handles:
    - ``#horizontalrule`` -> inline ``line()`` block.
      Pandoc emits this symbol for Markdown ``---`` separators but never
      defines it, causing ``error: unknown variable: horizontalrule``.

    Args:
        typ_path: Path to the .typ file to patch (modified in place).
    """
    content = typ_path.read_text(encoding="utf-8")
    patched = re.sub(r"#horizontalrule\b", _HRULE_TYPST, content)
    if patched != content:
        typ_path.write_text(patched, encoding="utf-8")


# ============================================================
# EXECUTION OF SUB-PROCESSES
# ============================================================


def _run(cmd: list[str], *, verbose: bool, label: str) -> None:
    """
    Executes a command and raises a RuntimeError if it fails.

    Args:
        cmd:     Command and arguments.
        verbose: If True, displays stdout and stderr even on success.
        label:   Tool name for the error message.

    Raises:
        RuntimeError: if the return code is non-zero.
    """
    result = subprocess.run(cmd, capture_output=True, text=True)
    if verbose or result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed (code {result.returncode}).\n"
            f"  Command : {' '.join(cmd)}\n"
            "  Use --verbose to display complete logs."
        )


# ============================================================
# MODE 1 - PDF BRUT (sans template)
# ============================================================


def to_pdf_raw(
    src: Path,
    dst: Path,
    *,
    emoji_json: Path | None = None,
    verbose: bool = False,
) -> None:
    """
    Markdown to PDF conversion using Pandoc + Typst, without a Typst template.

    Applies the full Python preprocessing pipeline before conversion:
    wikilink resolution, Obsidian callout conversion, emoji shortcode
    substitution (if emoji_json is provided), and spacing normalization.

    Pipeline:
        1. Python preprocessing (wikilinks, callouts, emojis, spacing)
        2. Pandoc: preprocessed .md -> .typ  (no template)
        3. Post-processing: fix #horizontalrule incompatibility
        4. Typst compile: .typ -> .pdf

    Args:
        src:        Source Markdown file (Obsidian).
        dst:        Output PDF file (created or overwritten).
        emoji_json: JSON emoji mapping. Default: assets/emojis.json.
                    Pass a missing path to emit a UserWarning and skip substitution.
        verbose:    Displays Pandoc and Typst logs on stdout/stderr.

    Raises:
        FileNotFoundError: if src cannot be found.
        RuntimeError:      if Pandoc or Typst fails (exit code non-zero).
        UserWarning:       if emoji_json path does not exist (non-fatal).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # Step 1 - Python pre-processing
        preprocessed_md = _prepare_conversion(src, dst, tmp, emoji_json)

        # Step 2 - Pandoc: Markdown -> Typst source
        out_typ = tmp / "doc.typ"
        # Delete the .typ file if it already exists
        if out_typ.exists():
            out_typ.unlink()

        _run(
            ["pandoc", str(preprocessed_md), "-t", "typst", "-o", str(out_typ), "--wrap=none"],
            verbose=verbose,
            label="pandoc",
        )

        # Step 3 - Post-processing: resolving incompatibilities between Pandoc and Typst
        if out_typ.exists():
            _fix_typst_output(out_typ)

        # Step 4 - Typst: .typ -> PDF
        _run(
            ["typst", "compile", str(out_typ), str(dst)],
            verbose=verbose,
            label="typst",
        )


# ============================================================
# MODE 2 - PDF AVEC TEMPLATE TYPST (pipeline complet)
# ============================================================


def to_pdf_typst(
    src: Path,
    dst: Path,
    *,
    template: Path | None = None,
    emoji_json: Path | None = None,
    verbose: bool = False,
) -> None:
    """
    Complete Obsidian Markdown -> PDF pipeline using the Typst template.

    Steps:
        1. Python pre-processing (wikilinks, callouts, optional emojis).
        2. Pandoc: Pre-processed Markdown -> .typ (using the eink.typ template).
        3. Typst: .typ -> PDF.

    Args:
        src:        Source Markdown file (Obsidian).
        dst:        Output PDF file.
        template:   Typst template (.typ). Default: assets/eink.typ.
        emoji_json: JSON emoji mapping. Default: assets/emojis.json.
                    Pass None to disable substitution.
        verbose:    Displays Pandoc and Typst logs.

    Raises:
        FileNotFoundError: if src or the template cannot be found.
        RuntimeError:      if Pandoc or Typst fails.
    """
    # Delete the output file if it already exists
    if dst.exists():
        dst.unlink()

    resolved_template = template or default_typst_template()
    if not resolved_template.exists():
        raise FileNotFoundError(
            f"Template 'Typst' not found: {resolved_template}\n"
            "  -> Create assets/eink.typ or pass template=Path('my_template.typ')"
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # Step 1 - Python pre-processing
        preprocessed_md = _prepare_conversion(src, dst, tmp, emoji_json)

        # Step 2 - Pandoc: Markdown -> Typst source
        out_typ = tmp / "doc.typ"

        # Delete the .typ file if it already exists
        if out_typ.exists():
            out_typ.unlink()

        _run(
            [
                "pandoc",
                str(preprocessed_md),
                "-t",
                "typst",
                "--template",
                str(resolved_template),
                "-o",
                str(out_typ),
                "--wrap=none",
            ],
            verbose=verbose,
            label="pandoc",
        )

        # Step 3 - Post-processing: resolving incompatibilities between Pandoc and Typst
        if out_typ.exists():
            _fix_typst_output(out_typ)

        # Step 4 - Typst: .typ -> PDF
        _run(
            ["typst", "compile", str(out_typ), str(dst)],
            verbose=verbose,
            label="typst",
        )


# ============================================================
# STRATEGY PATTERN
# ============================================================


class ConversionStrategy(Protocol):
    """Standard terms and conditions applicable to all Markdown to PDF conversion services."""

    def convert(self, src: Path, dst: Path) -> None:
        """
        Converts src to PDF and writes it to dst.

        Args:
            src: Source Markdown file.
            dst: Output PDF file (created or overwritten).

        Raises:
            FileNotFoundError: if src or a required resource cannot be found.
            RuntimeError: if a subprocess (Pandoc, Typst…) fails.
        """
        ...  # pragma: no cover


class RawStrategy:
    """Raw format: Pandoc -> Typst -> PDF, without a template."""

    def __init__(
        self,
        *,
        emoji_json: Path | None = None,
        verbose: bool = False,
    ) -> None:
        self._emoji_json = emoji_json
        self._verbose = verbose

    def convert(self, src: Path, dst: Path) -> None:
        to_pdf_raw(src, dst, emoji_json=self._emoji_json, verbose=self._verbose)


class TypstStrategy:
    """Full workflow: Pandoc -> Typst (using the eink.typ template) -> PDF."""

    def __init__(
        self,
        *,
        template: Path | None = None,
        emoji_json: Path | None = None,
        verbose: bool = False,
    ) -> None:
        self._template = template
        self._emoji_json = emoji_json
        self._verbose = verbose

    def convert(self, src: Path, dst: Path) -> None:
        to_pdf_typst(
            src,
            dst,
            template=self._template,
            emoji_json=self._emoji_json,
            verbose=self._verbose,
        )


def make_strategy(config: dict) -> ConversionStrategy:
    """
    Instantiates the conversion strategy described in config.

    Args:
        config: Parsed configuration (config.yaml). Recognised keys:
                - pdf_mode      : "raw" | "eink"  (default: "eink")
                - typst_template: path to the .typ template (eink mode)
                - emoji_json    : path to emojis.json
                - verbose       : bool

    Returns:
        A ready-to-use instance of ConversionStrategy.

    Raises:
        ValueError: if pdf_mode is unknown.
    """
    mode: str = config.get("pdf_mode", "eink")
    emoji_json: Path | None = Path(p) if (p := config.get("emoji_json")) else None
    verbose: bool = bool(config.get("verbose", False))

    if mode == "raw":
        return RawStrategy(emoji_json=emoji_json, verbose=verbose)

    if mode == "eink":
        template: Path | None = Path(t) if (t := config.get("typst_template")) else None
        return TypstStrategy(template=template, emoji_json=emoji_json, verbose=verbose)

    raise ValueError(f"Unknown PDF mode: {mode!r}\n" "  -> Accepted values: 'raw', 'eink'")
