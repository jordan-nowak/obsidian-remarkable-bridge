"""
Visual check of the converter.py pipeline (Typst).

Automatically reads all .md files in scripts/samples/
and converts them in both available modes.

Usage:
    python scripts/check_converter.py                   # all .md files, both modes
    python scripts/check_converter.py --mode raw        # raw mode only
    python scripts/check_converter.py --mode eink       # eink mode only
    python scripts/check_converter.py --no-open
    python scripts/check_converter.py --verbose

Output:
    <project_root>/.converter_check/
    ├── full_raw.pdf
    ├── full_eink.pdf
    ├── sample_converter_raw.pdf
    ├── sample_converter_eink.pdf
    └── ...

Prerequisites:
    - pandoc ≥ 3.1 in the PATH   (pandoc --list-output-formats | grep typst)
    - typst  ≥ 0.11 in the PATH  (https://github.com/typst/typst/releases)
    - src/orsync/assets/eink.typ  (Typst template provided in the repository)
    - src/orsync/assets/emojis.json  (emoji mapping provided in the repository)
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
from pathlib import Path

from orsync.converter import (
    default_emoji_json,
    default_typst_template,
    to_pdf_raw,
    to_pdf_typst,
)
from orsync.setup_check import check_pandoc, check_typst

# ============================================================
# PATHS
# ============================================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SAMPLES_DIR = SCRIPT_DIR / "samples"
OUTPUT_DIR = PROJECT_ROOT / ".converter_check"

MODES = ("raw", "eink")

# ============================================================
# DISPLAY HELPERS
# ============================================================


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ============================================================
# EXPLORING THE TEST FILES
# ============================================================


def _discover_samples() -> list[Path]:
    """Returns all .md files present in scripts/samples/, sorted."""
    if not SAMPLES_DIR.exists():
        return []
    return sorted(SAMPLES_DIR.glob("*.md"))


# ============================================================
# VERIFICATION OF DEPENDENCIES
# ============================================================


def _check_deps() -> bool:
    """Verifies pandoc, typst and the assets. Returns True if everything is OK."""
    ok = True

    try:
        version = check_pandoc()
        _ok(f"pandoc found: {version}")
    except EnvironmentError as exc:
        _fail(str(exc))
        ok = False

    # typst
    try:
        version = check_typst()
        _ok(f"typst found: {version}")
    except EnvironmentError as exc:
        _fail(str(exc))
        ok = False

    # template Typst
    template = default_typst_template()
    if template.exists():
        _ok(f"Template Typst: {template}")
    else:
        _warn(
            f"Template Typst not found : {template}\n"
            "         'eink' mode will fail. 'raw' mode remains functional."
        )

    # emojis.json
    emoji_json = default_emoji_json()
    if emoji_json.exists():
        import json

        try:
            mapping = json.loads(emoji_json.read_text(encoding="utf-8"))
            _ok(f"emojis.json   : {len(mapping)} inputs - {emoji_json}")
        except Exception as exc:
            _warn(f"emojis.json illegible: {exc}")
    else:
        _warn(
            f"emojis.json not found : {emoji_json}\n"
            "         The :smile: shortcodes will not be replaced."
        )

    return ok


# ============================================================
# OPENING THE OUTPUT DIRECTORY
# ============================================================


def _open_dir(path: Path) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))
    elif system == "Darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}"')


# ============================================================
# CONVERSIONS
# ============================================================


def _run_raw(src: Path, out_dir: Path, *, verbose: bool) -> Path | None:
    dst = out_dir / f"{src.stem}_raw.pdf"
    try:
        to_pdf_raw(src, dst, verbose=verbose)
        size_kb = dst.stat().st_size // 1024
        _ok(f"{src.name:30s} -> {dst.name}  ({size_kb} Ko)")
        return dst
    except (RuntimeError, FileNotFoundError) as exc:
        _fail(f"{src.name:30s} -> {exc}")
        return None


def _run_eink(src: Path, out_dir: Path, *, verbose: bool) -> Path | None:
    dst = out_dir / f"{src.stem}_eink.pdf"
    try:
        to_pdf_typst(src, dst, verbose=verbose)
        size_kb = dst.stat().st_size // 1024
        _ok(f"{src.name:30s} -> {dst.name}  ({size_kb} Ko)")
        return dst
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        _fail(f"{src.name:30s} -> {exc}")
        return None


# ============================================================
# ENTRY POINT
# ============================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visual verification of the Markdown -> PDF (Typst) pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default=None,
        help="Mode of conversion (default: all).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the output directory automatically.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Display complete Pandoc and Typst logs.",
    )
    args = parser.parse_args()

    modes_to_run = [args.mode] if args.mode else list(MODES)

    # ── Discovery of test files ──
    samples = _discover_samples()
    if not samples:
        print(f"\n[ERROR] No .md files found in : {SAMPLES_DIR}")
        print("         Add at least one .md file to this directory.")
        sys.exit(1)

    print(f"\nOutput directory : {OUTPUT_DIR}")
    print(f"Files found  : {len(samples)} .md in {SAMPLES_DIR}")

    # ── Checking dependencies ──
    _section("Checking dependencies")
    if not _check_deps():
        _fail("Missing critical dependencies - shutdown.")
        sys.exit(1)

    # ── Test files ──
    _section("Test files detected")
    for s in samples:
        _ok(s.name)

    # ── Conversions ──
    runners = {
        "raw": _run_raw,
        "eink": _run_eink,
    }
    labels = {
        "raw": "Mode raw  - preprocessing + Pandoc + Typst without template",
        "eink": "Mode eink - preprocessing + Pandoc + Typst with template eink.typ",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Path | None]] = {m: {} for m in modes_to_run}

    for mode in modes_to_run:
        _section(labels[mode])
        for src in samples:
            results[mode][src.stem] = runners[mode](src, OUTPUT_DIR, verbose=args.verbose)

    # ── Resume ──
    _section("Resume")
    all_ok = True
    for mode in modes_to_run:
        print(f"\n  [{mode.upper()}]")
        for stem, pdf in results[mode].items():
            if pdf is not None:
                _ok(f"{stem:25s} -> {pdf.name}")
            else:
                _fail(f"{stem:25s} -> failure")
                all_ok = False

    # ── Ouverture du dossier ──
    if not args.no_open and any(v is not None for m in results.values() for v in m.values()):
        print("\n  Opening output directory for inspection...")
        _open_dir(OUTPUT_DIR)

    print()
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
