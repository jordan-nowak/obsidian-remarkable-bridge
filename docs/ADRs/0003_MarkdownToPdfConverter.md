---
date: 08-APR-2026
ref: 0003
author: JNO
---

# [0003]_MarkdownToPdfConverter

## Context

The sync pipeline must convert `.md` files from the Obsidian vault into PDFs before uploading them to the reMarkable 2. The tablet has an e-ink screen: PDFs generated for print (A4, small margins, dense text) are poorly readable on it. Two distinct rendering modes are therefore required.

**Mode `raw`:**
Pandoc + Typst, without a Typst template. Produces a plain PDF directly from the Pandoc Typst output. Used as a lightweight baseline and for CI validation.

**Mode `eink`:**
Full pipeline with the bundled `eink.typ` Typst template:

```
.md  ──Python preprocessing──>  .md  ──Pandoc──>  .typ  ──Typst──>  .pdf
```

The template controls typography, heading styles, margins, line height, and emoji rendering - all optimised for e-ink readability.

**Why Typst over WeasyPrint (initial design):**
The original solution proposed WeasyPrint (HTML -> PDF). This was replaced by Typst during implementation because:

- WeasyPrint not work correctly on mathematical bloc.
- Typst is a single binary, pip-free, cross-platform, and already required by `setup_check.py` as a system dependency.
- Pandoc 3.x has native Typst output (`-t typst`), eliminating the HTML intermediate step entirely.
- The Typst template gives equivalent visual control over layout, fonts, and emoji handling with less toolchain complexity.

**Obsidian-specific preprocessing:**
Pandoc does not understand Obsidian syntax. A Python preprocessing layer runs before Pandoc on all modes:

| Transformation | Input | Output |
|---|---|---|
| Wikilinks | `[[Note]]`, `[[Note\|Alias]]` | Standard Markdown links |
| Embeds | `![[file.md]]` | `*(embed: file.md)*` text marker |
| Callouts | `> [!warning] Title` | `> **⚠️ Warning - Title**` blockquote |
| Emoji shortcodes | `:smile:` | `😄` (via `emojis.json`) |
| List spacing | List item after non-blank non-list line | Blank line inserted before |
| Blockquote spacing | Bold header immediately followed by body | `> ` blank line inserted |

**Pandoc/Typst compatibility:**
Pandoc emits `#horizontalrule` for Markdown `---` separators but does not define it, causing `error: unknown variable: horizontalrule` in recent Typst versions. A post-processing step replaces every occurrence with an inline `line()` block before handing the file to `typst compile`.

## Decision

Implement `converter.py` exposing the following public interface:

```python
# Asset path helpers
def default_typst_template() -> Path: ...   # assets/eink.typ
def default_emoji_json() -> Path: ...       # assets/emojis.json

# Conversion functions
def to_pdf_raw(
    src: Path,
    dst: Path,
    *,
    emoji_json: Path | None = None,
    verbose: bool = False,
) -> None: ...

def to_pdf_typst(
    src: Path,
    dst: Path,
    *,
    template: Path | None = None,
    emoji_json: Path | None = None,
    verbose: bool = False,
) -> None: ...

# Strategy pattern
class ConversionStrategy(Protocol):
    def convert(self, src: Path, dst: Path) -> None: ...

class RawStrategy:    ...   # wraps to_pdf_raw
class TypstStrategy:  ...   # wraps to_pdf_typst

def make_strategy(config: dict) -> ConversionStrategy: ...
```

**`to_pdf_raw(src, dst)`** - Pandoc + Typst without a template. 
Raises `FileNotFoundError` if `src` is missing, `RuntimeError` if Pandoc or Typst returns a non-zero exit code (stderr surfaced in message), `UserWarning` (non-fatal) if `emojis.json` cannot be found.

**`to_pdf_typst(src, dst)`** - Full pipeline with `eink.typ` template.
Raises `FileNotFoundError` if `src` or the resolved template is missing, `RuntimeError` on Pandoc or Typst failure.

**`make_strategy(config)`** - instantiates the correct strategy from
`config.yaml`. Recognised key: `pdf_mode: "raw" | "eink"` (default: `"eink"`). Raises `ValueError` for unknown modes.

**`css` / WeasyPrint parameter removed** - the original ADR described a
`css: Path | None` parameter on `to_pdf_eink`. This is no longer applicable; the equivalent is `template: Path | None` on `to_pdf_typst`.

**Internal helpers (not part of the public API):**

```python
def _assets_dir() -> Path: ...
def _preprocess_wikilinks(text: str) -> str: ...
def _preprocess_callouts(text: str) -> str: ...
def _preprocess_spacing(text: str) -> str: ...
def _preprocess_emojis(text: str, emoji_map: dict[str, str]) -> str: ...
def _preprocess(src: Path, *, emoji_json: Path | None = None) -> str: ...
def _prepare_conversion(src, dst, tmp, emoji_json) -> Path: ...
def _fix_typst_output(typ_path: Path) -> None: ...
def _run(cmd: list[str], *, verbose: bool, label: str) -> None: ...
```

## Pipeline Detail

**`to_pdf_raw` pipeline:**

```
src (.md)
  │
  ├ Step 1 - _prepare_conversion()
  │   FileNotFoundError if src missing
  │   Resolves emoji_json (default: assets/emojis.json, UserWarning if absent)
  │   Creates dst.parent/
  │   Applies _preprocess() -> writes tmp/preprocessed.md
  │
  ├ Step 2 - Pandoc
  │   pandoc tmp/preprocessed.md -t typst -o tmp/doc.typ --wrap=none
  │   RuntimeError on non-zero exit
  │
  ├ Step 3 - _fix_typst_output()
  │   Replaces #horizontalrule -> inline line() block
  │
  ├ Step 4 - Typst
    typst compile tmp/doc.typ dst
    RuntimeError on non-zero exit
```

**`to_pdf_typst` pipeline:**

```
src (.md)
  │
  ├ Step 1 - _prepare_conversion()   (same as raw)
  │
  ├ Step 2 - Pandoc (with template)
  │   pandoc tmp/preprocessed.md -t typst
  │         --template assets/eink.typ
  │         -o tmp/doc.typ --wrap=none
  │   FileNotFoundError if template missing
  │   RuntimeError on non-zero exit
  │
  ├ Step 3 - _fix_typst_output()     (same as raw)
  │
  ├ Step 4 - Typst
    typst compile tmp/doc.typ dst
    RuntimeError on non-zero exit
```

Both pipelines use `tempfile.TemporaryDirectory()` - all intermediate files
(preprocessed Markdown, `.typ` source) are cleaned up automatically.

## Template and Assets - `eink.typ` design intent

| Property | Value | Rationale |
|---|---|---|
| Page size | A5 | Matches rM2 screen ratio |
| Margins | 20mm all sides | Leaves room for annotations |
| Font size | 14pt body | Comfortable on rM2 screen |
| Font family | Serif fallback | Better legibility on e-ink |
| Heading colour | Dark grey `#222` | Avoids harsh black-on-white contrast |
| Line height | 1.6 | Reduces eye strain |
| Code blocks | Monospace, light background | Distinguishable on e-ink |
| Emoji support | NotoColorEmoji font (bundled) | Loaded via Typst `@font-face` equivalent |

Asset structure:

```
src/orsync/assets/
├── eink.typ             Typst template for eink mode
└── emojis.json          name -> Unicode mapping  {"smile": "😄", ...}
```

## Implementation

Branch: `feature/0003_MarkdownToPdfConverter`

Commit: `[0003] feat(converter): implement raw and eink markdown to pdf conversion`

Implementation file: `src/orsync/converter.py`

**Key technical choices:**

- `subprocess.run` with `capture_output=True` - stderr surfaced in `RuntimeError` on failure; printed unconditionally in verbose mode.
- `tempfile.TemporaryDirectory()` as context manager - all intermediate files deleted on success and on error.
- `shutil.which` not called explicitly in `converter.py` - binary availability is guaranteed upstream by `setup_check.py`; `RuntimeError` from `_run` is sufficient if a binary disappears mid-session.
- `_fix_typst_output` runs on both modes after Pandoc - the `#horizontalrule` incompatibility is not template-dependent.
- Strategy pattern (`ConversionStrategy` Protocol, `RawStrategy`, `TypstStrategy`, `make_strategy`) - the CLI selects the strategy once from config and passes it through the pipeline without knowing the mode.

**`pyproject.toml` additions:**

```toml
[tool.setuptools.package-data]
orsync = ["assets/eink.typ", "assets/emojis.json"]
```

No optional dependencies - Typst is a system binary, not a Python package.

## Related Tests

All unit tests are implemented in `tests/unit/test_converter.py` and cover `converter.py` according to the following structure:

```
UNIT TESTS
0. Fixtures & Setup
1. Constructor & Initialization   - RawStrategy, TypstStrategy, make_strategy
2. Accessors                      - default_typst_template, default_emoji_json, _assets_dir
3. Main Methods                   - to_pdf_raw, to_pdf_typst, each preprocessing helper
4. Fundamental Behavior           - preprocessing idempotence, fix_typst_output correctness
5. Special Cases & Tolerance      - missing emojis.json (UserWarning), missing template
6. Regression & Non-Regression

INTEGRATION TESTS
7. Interface contract             - output of to_pdf_typst consumed by sync pipeline
```

**CI pipeline requirements:**

- Tests run on Ubuntu and Windows
- Compatible with Python 3.11, 3.12, 3.13
- All `subprocess.run` calls mocked - no Pandoc or Typst binary required in CI
- No regression allowed

## Known Issues

**Typst warning on auto-generated label:**
Pandoc generates an anchor label for the document title (e.g. `<sample-note-converter-rendering-check>`) that triggers a Typst warning `"label not attached to anything"`. Impact: none - the PDF is generated correctly. 
Decision: accepted as-is; suppressing the warning would require non-trivial post-processing of the `.typ` file for zero functional gain.

## Risks/Impacts

- **Pandoc not in PATH** - `_run` raises `RuntimeError` surfacing Pandoc stderr. `setup_check.py` detects this at startup. Documented in README.
- **Typst not in PATH** - same pattern.
- **`emojis.json` missing** - non-fatal `UserWarning`; shortcodes are preserved as-is in the output.
- **Impact on `sync.py` (CLI)** - the CLI calls `strategy.convert(src, dst)`; a `RuntimeError` from either mode must abort the current note's sync without crashing the full pipeline.
- **Impact on `pyproject.toml`** - `assets/` must be declared under `[tool.setuptools.package-data]` to be included in the installed package.

[<-- 0002_VaultScanner](0002_VaultScanner.md) · [0004_IncrementalSyncEngine -->](0004_IncrementalSyncEngine.md)