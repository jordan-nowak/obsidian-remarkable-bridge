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

run_check(config) -> CheckReport:
1. Detect the OS
2. Search for pandoc in the PATH
   - Found -> Check the pandoc version
     - returncode == 0 -> CheckItem True, version retrieved
     - returncode != 0 -> CheckItem False, version not retrieved
   - Not found -> CheckItem False, do not call subprocess + provide installation guidance
3. Attempt USB SSH connection
   - Success -> CheckItem True
   - Failure -> CheckItem False (no raise)
4. If ip_wifi is not empty: attempt WiFi SSH connection
   Otherwise: CheckItem True with detail "skipped"
5. If USB (or WiFi) succeeded: read the tablet's version
   - Success -> CheckItem True
   - Failure -> CheckItem False with detail "error"
   Otherwise: CheckItem False with detail "skipped - no SSH connection available"
6. If conversion_mode in (raw, both): check XeLaTeX
   - shutil.which("xelatex") found -> run xelatex --version
     - returncode == 0 -> CheckItem True, version retrieved
     - returncode != 0 -> CheckItem False
     - timeout -> CheckItem False
   - Not found -> CheckItem False + installation guidance (TeX Live / MiKTeX)
   Otherwise: CheckItem True with detail "skipped - mode is eink"
7. If conversion_mode in (eink, both): check WeasyPrint
   - import weasyprint fails -> CheckItem False + pip install guidance
   - import ok -> run write_pdf() on minimal HTML string
     - success -> CheckItem True, version retrieved
     - raises -> CheckItem False + GTK install guidance (Windows)
   Otherwise: CheckItem True with detail "skipped - mode is raw"

Fundamental rule: no check interrupts the subsequent ones. The caller checks report.all_ok to decide whether to abort the pipeline.

### `vault.py` - Algorithm

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

resolve_wikilinks_in_file(md_path, vault_path) -> str:
1. md_path does not exist -> raise FileNotFoundError
2. vault_path invalid -> raise ValueError (delegated to scan_vault via _build_index)
3. Build index via _build_index(vault_path)
4. Read file content (UTF-8)
5. Apply _resolve_wikilinks(content, index, md_path)
6. Return resolved content

vault_tree(vault_path) -> str:
1. Call scan_vault(vault_path) - raises ValueError if invalid
2. For each file (sorted), compute relative path from vault_path
3. Track seen intermediate directories to avoid duplicates
4. Build lines with "│" "├──" "└──" indentation
5. Return joined string

### `converter.py` - Algorithm

_assets_dir() -> Path:
  Return Path(__file__).parent / "assets"

_default_css() -> Path:
  Return _assets_dir() / "eink.css"

_run_pandoc(args, timeout) -> None:
1. subprocess.run(args, capture_output=True, text=True, timeout=timeout)
   - TimeoutExpired -> raise RuntimeError("timed out after {timeout}s")
2. returncode != 0 -> raise RuntimeError("Pandoc failed (exit {code}): {stderr}")

check_pandoc() -> None:
1. shutil.which("pandoc") is None -> raise EnvironmentError (with pandoc.org install URL)

to_pdf_raw(md_path, output_path) -> None:
1. md_path does not exist -> raise FileNotFoundError
2. _run_pandoc(["pandoc", md_path, "-o", output_path, "--pdf-engine=lualatex"])
   - RuntimeError propagates to caller

to_pdf_eink(md_path, output_path, css=None) -> None:
1. md_path does not exist -> raise FileNotFoundError
2. resolved_css = css if css is not None else _default_css()
3. resolved_css does not exist -> raise FileNotFoundError
4. import weasyprint
   - ImportError -> raise ImportError (with pip install hint)
5. tmp_html = output_path.with_suffix(".html")
6. try:
     _run_pandoc(["pandoc", md_path, "-t", "html", "-o", tmp_html, "--standalone"])
     weasyprint.HTML(filename=tmp_html).write_pdf(
         output_path,
         stylesheets=[weasyprint.CSS(filename=resolved_css)]
     )
   finally:
     if tmp_html.exists() -> tmp_html.unlink()

---

[<-- Software Architecture](./01_Software_Architecture.md) · [Validation Plan -->](./03_Validation_Plan.md)