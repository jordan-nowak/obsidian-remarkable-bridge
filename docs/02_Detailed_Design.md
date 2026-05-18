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

```
run_check(config) -> CheckReport:
  1. _build_context(config)
       Extracts and normalises config values into a frozen _CheckContext dataclass
  2. _build_checklist(ctx)
       Constructs the ordered list of zero-argument check callables:
         Step 1 - _check_os()
         Step 2 - check_pandoc()      via _check_binary
         Step 3 - ssh_usb_cached()    SSH USB (executed eagerly here, result cached)
         Step 4 - ssh_wifi_cached()   SSH WiFi (skipped if ip_wifi absent or empty)
         Step 5 - firmware_check()    reads /etc/version via SSH (USB first, WiFi fallback)
         Step 6 - check_typst()       via _check_binary
  3. _execute(checks)
       Runs each callable sequentially
       Each check is wrapped in try/except - any unexpected exception becomes a failed CheckItem
       Returns CheckReport(items=[...])
```

**SSH / firmware dependency resolution:**
SSH checks (USB and WiFi) are executed **eagerly** during `_build_checklist`, not lazily during `_execute`. Their results are cached in closures and replayed when `_execute` calls the returned callables. This avoids opening two SSH connections to the same host and allows `firmware_ip` to be resolved before the checklist is returned. The firmware check reuses the first successful SSH connection (USB takes precedence over WiFi).

**_check_binary(name, args, not_found_detail):**
A shared helper checks any CLI binary: `shutil.which` for PATH presence, then `subprocess.run` with `capture_output=True, timeout=5`. The first line of stdout is used as the version string. Covers both `check_pandoc()` and `check_typst()`.

**Fundamental rule:** no check interrupts the subsequent ones. The caller checks `report.all_ok` to decide whether to abort the pipeline.

---

### `vault.py` - Algorithm

```
scan_vault(vault_path) -> list[Path]:
  1. Check vault_path exists
     - Does not exist -> raise ValueError
     - Not a directory -> raise ValueError
  2. Recurse with rglob("*.md")
  3. Return sorted list of absolute paths

_build_index(vault_path) -> dict[str, stem -> Path]:
  1. Recurse with rglob("*.md")
  2. For each file:
     - stem not in index -> add to index
     - stem already in index -> mark stem as duplicate, do NOT add
  3. Remove all duplicate stems from index
  4. Return index (unique stems only)
     Note: duplicate stems are intentionally excluded - a [[wikilink]]
     targeting an ambiguous stem must fall back to plain text.

_resolve_wikilinks(content, index, source) -> str:
  For each [[raw]] match (regex: \[\[([^\[\]]+)\]\]):
    - Split raw on "|" (max 1 split)
      - 1 part  -> target_stem = label = raw
      - 2 parts -> target_stem = parts[0], label = parts[1]
    - target_stem in index
      -> compute relative path from source.parent to index[target_stem]
      -> replace with [label](relative_path)
    - target_stem not in index (missing or duplicate)
      -> replace with plain text label (no brackets)

resolve_wikilinks_in_file(md_path, vault_path, *, index=None) -> str:
  1. md_path does not exist -> raise FileNotFoundError
  2. vault_path invalid -> raise ValueError (delegated to scan_vault via _build_index)
  3. Use provided index or build via _build_index(vault_path)
  4. Read file content (UTF-8)
  5. Apply _resolve_wikilinks(content, index, md_path)
  6. Return resolved content

vault_tree(vault_path) -> str:
  1. Call scan_vault(vault_path) - raises ValueError if invalid
  2. For each file (sorted), compute relative path from vault_path
  3. Track seen intermediate directories to avoid duplicates
  4. Build lines with "│" "├──" "└──" indentation
  5. Return joined string
```

---

### `converter.py` - Algorithm

#### Asset helpers

```
_assets_dir() -> Path:
  Return Path(__file__).parent / "assets"

default_typst_template() -> Path:
  Return _assets_dir() / "eink.typ"

default_emoji_json() -> Path:
  Return _assets_dir() / "emojis.json"
```

#### Preprocessing pipeline

All preprocessing runs before Pandoc, on every conversion mode.

```
_preprocess_callouts(text) -> str:
  Replaces > [!type] Title callout headers with icon-prefixed bold blockquotes.
  Known types and icons: note 📝, info ℹ️, tip 💡, warning ⚠️, danger 🔥,
    error ❌, success ✅, question ❓, quote 💬, abstract 📋.
  Unknown types fall back to 📌. Case-insensitive. No-op on standard blockquotes.

_preprocess_spacing(text) -> str:
  Two rules applied in a single line-by-line pass (code fences are skipped):
  Rule 1 - List spacing:
    A list item not preceded by a blank line or another list item
    gets a blank line inserted before it.
  Rule 2 - Blockquote body spacing:
    A bold callout header ("> **...**") immediately followed by a body line
    ("> text") gets a "> " blank line inserted between them.
  Code fence detection: backtick (```) and tilde (~~~) fences are tracked;
    rules are disabled inside fences.

_preprocess_wikilinks(text) -> str:
  ![[embed.md]]            -> *(embed: embed.md)*
  [[Target|Alias]]         -> [Alias](Target.md)
  [[Target]]               -> [Target](Target.md)

_preprocess_emojis(text, emoji_map) -> str:
  Replaces :shortcode: with Unicode codepoint from emoji_map.
  Unknown shortcodes are preserved unchanged.

_preprocess(src, *, emoji_json=None) -> str:
  Applies in order: _preprocess_callouts -> _preprocess_spacing
    -> _preprocess_wikilinks -> _preprocess_emojis (if emoji_json provided).
  Returns preprocessed Markdown string.
```

#### Shared setup

```
_prepare_conversion(src, dst, tmp, emoji_json) -> Path:
  1. src does not exist -> raise FileNotFoundError
  2. Resolve emoji_json:
     - None -> default_emoji_json()
     - resolved path does not exist -> emit UserWarning (non-fatal), proceed without emojis
  3. dst.parent.mkdir(parents=True, exist_ok=True)
  4. Apply _preprocess(src, emoji_json=emoji_path) -> write to tmp/preprocessed.md
  5. Return tmp/preprocessed.md
```

#### Post-processing

```
_fix_typst_output(typ_path) -> None:
  Reads the .typ file produced by Pandoc.
  Replaces every occurrence of #horizontalrule with an inline Typst line() block.
  Reason: Pandoc emits #horizontalrule for --- separators but never defines it,
    causing "error: unknown variable: horizontalrule" in recent Typst versions.
  No-op if #horizontalrule is absent (file not rewritten).
```

#### Conversion modes

```
to_pdf_raw(src, dst, *, emoji_json=None, verbose=False) -> None:
  Pipeline:
    1. _prepare_conversion(src, dst, tmp, emoji_json)
       FileNotFoundError if src missing
       UserWarning if emoji_json path does not exist (non-fatal)
    2. Delete tmp/doc.typ if it already exists
    3. Pandoc: pandoc preprocessed.md -t typst -o doc.typ --wrap=none
       RuntimeError on non-zero exit code (stderr surfaced in message)
    4. _fix_typst_output(doc.typ)
    5. Typst: typst compile doc.typ dst
       RuntimeError on non-zero exit code
  Intermediate files managed by tempfile.TemporaryDirectory (auto-cleaned on exit)

to_pdf_typst(src, dst, *, template=None, emoji_json=None, verbose=False) -> None:
  Pipeline:
    0. Delete dst if it already exists
    1. Resolve template: None -> default_typst_template()
       FileNotFoundError if resolved template does not exist
    2. _prepare_conversion(src, dst, tmp, emoji_json)
    3. Delete tmp/doc.typ if it already exists
    4. Pandoc: pandoc preprocessed.md -t typst --template eink.typ -o doc.typ --wrap=none
       FileNotFoundError if template missing (raised before Pandoc call)
       RuntimeError on non-zero exit code
    5. _fix_typst_output(doc.typ)
    6. Typst: typst compile doc.typ dst
       RuntimeError on non-zero exit code
  Intermediate files managed by tempfile.TemporaryDirectory (auto-cleaned on exit)
```

#### Strategy pattern

```
ConversionStrategy (Protocol):
  convert(src: Path, dst: Path) -> None

RawStrategy:
  Wraps to_pdf_raw with bound emoji_json and verbose parameters.

TypstStrategy:
  Wraps to_pdf_typst with bound template, emoji_json and verbose parameters.

make_strategy(config: dict) -> ConversionStrategy:
  Reads pdf_mode from config (default: "eink").
  "raw"  -> RawStrategy(emoji_json=..., verbose=...)
  "eink" -> TypstStrategy(template=..., emoji_json=..., verbose=...)
  Other  -> raise ValueError
```

---

[<-- Software Architecture](./01_Software_Architecture.md) · [Validation Plan -->](./03_Validation_Plan.md)