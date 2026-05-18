"""
Unit and integration tests for `orsync.converter`.

Test structure:

UNIT TESTS
0. Fixtures & Setup
1. Asset Path Helpers
2. Preprocessors (_preprocess_* functions)
3. Main Methods - to_pdf_raw / to_pdf_typst
4. Strategy Pattern
5. Fundamental Behavior & Edge Cases
6. Regression & Non-Regression

INTEGRATION TESTS
7. Contract with setup_check (conversion pipeline prerequisites)
"""

from __future__ import annotations

from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from orsync.converter import (
    _preprocess,
    _preprocess_callouts,
    _preprocess_emojis,
    _preprocess_spacing,
    _preprocess_wikilinks,
    default_emoji_json,
    default_typst_template,
    make_strategy,
    to_pdf_raw,
    to_pdf_typst,
)

# ============================================================
# 0. FIXTURES & SETUP
# ============================================================


@pytest.fixture
def md_file(tmp_path: Path) -> Path:
    """Minimal valid .md file."""
    p = tmp_path / "note.md"
    p.write_text("# Hello\nSimple content.", encoding="utf-8")
    return p


@pytest.fixture
def md_file_with_emoji(tmp_path: Path) -> Path:
    """Markdown file containing native Unicode emojis."""
    p = tmp_path / "emoji.md"
    p.write_text("# Emojis\n\nNative emoji 🎯 and another 🚀\nEnd.", encoding="utf-8")
    return p


@pytest.fixture
def md_file_with_emoji_shortcodes(tmp_path: Path) -> Path:
    """Markdown file containing emoji shortcodes (:smile:)."""
    p = tmp_path / "shortcodes.md"
    p.write_text("# Shortcodes\n\nHello :smile: world :unknown_xyz:", encoding="utf-8")
    return p


@pytest.fixture
def md_file_with_table(tmp_path: Path) -> Path:
    """Markdown file containing a Markdown table."""
    p = tmp_path / "table.md"
    p.write_text(
        "# Table\n\n"
        "| Col A | Col B | Col C |\n"
        "|-------|-------|-------|\n"
        "| 1     | 2     | 3     |\n"
        "| 4     | 5     | 6     |",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def md_file_with_math(tmp_path: Path) -> Path:
    """Markdown file containing inline and block LaTeX formulas."""
    p = tmp_path / "math.md"
    p.write_text(
        "# Math\n\nInline: $E = mc^2$\n\nBlock:\n\n$$\n\\int_0^\\infty e^{-x} dx = 1\n$$",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def md_file_obsidian(tmp_path: Path) -> Path:
    """Markdown file using Obsidian syntax: wikilinks and callouts."""
    p = tmp_path / "obsidian.md"
    p.write_text(
        "# Obsidian Note\n\n"
        "Link: [[Other Note]]\n"
        "Alias: [[Target|My Alias]]\n"
        "Embed: ![[image.png]]\n\n"
        "> [!warning] Watch out\n"
        "> Callout body.",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def md_file_with_hrules(tmp_path: Path) -> Path:
    """Markdown file containing horizontal rule separators."""
    p = tmp_path / "hrules.md"
    p.write_text(
        "# Section A\n\nParagraph.\n\n---\n\n# Section B\n\nAnother paragraph.",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def output_pdf(tmp_path: Path) -> Path:
    """Target path for the generated PDF."""
    return tmp_path / "output.pdf"


@pytest.fixture
def typ_template(tmp_path: Path) -> Path:
    """Minimal valid Typst template."""
    p = tmp_path / "eink.typ"
    p.write_text('#include "body.typ"', encoding="utf-8")
    return p


@pytest.fixture
def emoji_json(tmp_path: Path) -> Path:
    """Minimal valid emojis.json file."""
    p = tmp_path / "emojis.json"
    p.write_text('{"smile": "😄", "wave": "👋", "fire": "🔥"}', encoding="utf-8")
    return p


@pytest.fixture
def mock_run_success():
    """subprocess.run always returns exit code 0.

    _fix_typst_output is also patched because it reads doc.typ from disk,
    a file that pandoc never creates when subprocess.run is mocked.
    Tests in section 3 verify subprocess call order and arguments, not
    the post-processing step - so bypassing _fix_typst_output is correct here.
    """
    with (
        patch("orsync.converter.subprocess.run") as mock_run,
        patch("orsync.converter._fix_typst_output"),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


@pytest.fixture
def mock_run_failure():
    """subprocess.run returns a non-zero exit code with stderr."""
    with patch("orsync.converter.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error: unknown output format",
        )
        yield mock_run


@pytest.fixture
def mock_run_timeout():
    """subprocess.run raises TimeoutExpired."""
    with patch(
        "orsync.converter.subprocess.run",
        side_effect=TimeoutExpired(cmd="pandoc", timeout=60),
    ):
        yield


# ============================================================
# 1. ASSET PATH HELPERS
# ============================================================


def test_default_typst_template_is_eink_typ():
    """default_typst_template() must return a Path pointing to assets/eink.typ."""
    result = default_typst_template()
    assert isinstance(result, Path)
    assert result.name == "eink.typ"
    assert result.parent.name == "assets"


def test_default_emoji_json_is_under_assets():
    """default_emoji_json() must return a Path pointing to assets/emojis.json."""
    result = default_emoji_json()
    assert isinstance(result, Path)
    assert result.name == "emojis.json"
    assert result.parent.name == "assets"


# ============================================================
# 2. PREPROCESSORS
# ============================================================


def test_preprocess_wikilinks_simple_link_becomes_markdown():
    """[[Note]] must be converted to [Note](Note.md)."""
    assert _preprocess_wikilinks("[[Note Title]]") == "[Note Title](Note Title.md)"


def test_preprocess_wikilinks_with_alias():
    """[[Target|Alias]] must be converted to [Alias](Target.md)."""
    assert _preprocess_wikilinks("[[Target|My Alias]]") == "[My Alias](Target.md)"


def test_preprocess_wikilinks_embed_replaced_by_textual_marker():
    """![[embed.png]] must be replaced by a textual marker (no wikilink syntax remaining)."""
    result = _preprocess_wikilinks("![[image.png]]")
    assert "[[" not in result
    assert "embed" in result
    assert "image.png" in result


def test_preprocess_wikilinks_no_false_positive_on_regular_markdown_link():
    """A standard Markdown link [text](url) must not be modified."""
    original = "[normal text](https://example.com)"
    assert _preprocess_wikilinks(original) == original


def test_preprocess_wikilinks_multiple_links_all_converted():
    """Multiple wikilinks in the same text must all be converted."""
    result = _preprocess_wikilinks("See [[Note A]] and [[Note B|B]].")
    assert "[Note A](Note A.md)" in result
    assert "[B](Note B.md)" in result


def test_preprocess_wikilinks_idempotent_on_plain_text():
    """_preprocess_wikilinks must be a no-op on text without wikilinks."""
    text = "Plain text without any special link syntax."
    assert _preprocess_wikilinks(text) == text


def test_preprocess_callouts_note_with_title_contains_icon_and_title():
    """> [!note] Title must produce the 📝 icon and the title."""
    result = _preprocess_callouts("> [!note] My title")
    assert "📝" in result
    assert "My title" in result


def test_preprocess_callouts_warning_contains_icon():
    """> [!warning] must produce the ⚠️ icon."""
    result = _preprocess_callouts("> [!warning] Watch out")
    assert "⚠️" in result


def test_preprocess_callouts_tip_no_title_no_separator():
    """> [!tip] with no title must produce 💡 without a dash separator."""
    result = _preprocess_callouts("> [!tip]")
    assert "💡" in result
    assert " - " not in result


def test_preprocess_callouts_unknown_type_uses_default_icon():
    """> [!custom] must use the fallback icon 📌."""
    result = _preprocess_callouts("> [!custom]")
    assert "📌" in result


@pytest.mark.parametrize(
    "kind, expected_icon",
    [
        ("note", "📝"),
        ("info", "ℹ️"),
        ("tip", "💡"),
        ("warning", "⚠️"),
        ("danger", "🔥"),
        ("error", "❌"),
        ("success", "✅"),
        ("question", "❓"),
        ("quote", "💬"),
        ("abstract", "📋"),
    ],
    ids=[
        "note",
        "info",
        "tip",
        "warning",
        "danger",
        "error",
        "success",
        "question",
        "quote",
        "abstract",
    ],
)
def test_preprocess_callouts_all_known_types_have_dedicated_icon(kind: str, expected_icon: str):
    """Each known callout type must produce its dedicated icon."""
    result = _preprocess_callouts(f"> [!{kind}]")
    assert expected_icon in result


def test_preprocess_callouts_case_insensitive():
    """> [!NOTE] (uppercase) must be treated identically to > [!note]."""
    result = _preprocess_callouts("> [!NOTE] Title")
    assert "📝" in result


def test_preprocess_callouts_does_not_alter_regular_blockquote():
    """A standard blockquote without [!type] must not be modified."""
    original = "> This is a normal blockquote."
    assert _preprocess_callouts(original) == original


def test_preprocess_spacing_inserts_blank_line_before_list_after_label():
    """A list item immediately after a non-list line must get a blank line inserted before it."""
    text = "Label:\n- item"
    result = _preprocess_spacing(text)
    lines = result.splitlines()
    list_index = next(i for i, line in enumerate(lines) if line.startswith("- "))
    assert lines[list_index - 1] == ""


def test_preprocess_spacing_does_not_insert_blank_between_consecutive_list_items():
    """Consecutive list items must not get an extra blank line between them."""
    text = "- item A\n- item B\n- item C"
    result = _preprocess_spacing(text)
    assert result.count("\n\n") == 0


def test_preprocess_spacing_inserts_blockquote_separator_after_bold_header():
    """A bold callout header immediately followed by a content line must get a '>' separator."""
    text = "> **📝 Note - Title**\n> Body text."
    result = _preprocess_spacing(text)
    lines = result.splitlines()
    # A bare "> " separator line must appear between the header and body
    assert ">" in lines


def test_preprocess_spacing_skips_rules_inside_code_fence():
    """List and blockquote rules must not be applied inside fenced code blocks."""
    text = "```\n- not a list\n> not a blockquote\n```"
    result = _preprocess_spacing(text)
    # Content inside the fence must remain unchanged
    assert "- not a list" in result
    assert "> not a blockquote" in result


def test_preprocess_spacing_exits_tilde_fence_correctly():
    """_preprocess_spacing must exit a ~~~ fence when the closing ~~~ is reached.

    Covers converter.py lines 165-168 (elif branch for fence closure).
    """
    text = "Before fence.\n~~~\n- list inside fence\n~~~\n- list outside fence"
    result = _preprocess_spacing(text)
    lines = result.splitlines()
    # The list item OUTSIDE the fence must receive a blank line before it
    outside_idx = next(i for i, line in enumerate(lines) if line == "- list outside fence")
    assert (
        lines[outside_idx - 1] == ""
    ), "A blank line must be inserted before the list item outside the fence"
    # The list item INSIDE the fence must not be altered
    assert "- list inside fence" in result


def test_preprocess_spacing_preserves_content_outside_affected_lines():
    """_preprocess_spacing must not alter text unrelated to spacing rules."""
    text = "# Title\n\nIntact content.\n\nOther content."
    result = _preprocess_spacing(text)
    assert "# Title" in result
    assert "Intact content." in result
    assert "Other content." in result


def test_preprocess_emojis_known_shortcode_is_replaced():
    """:smile: must be replaced by its Unicode codepoint."""
    assert _preprocess_emojis(":smile:", {"smile": "😄"}) == "😄"


def test_preprocess_emojis_unknown_shortcode_is_preserved():
    """:unknown: with no mapping entry must be left unchanged."""
    assert _preprocess_emojis(":unknown:", {"smile": "😄"}) == ":unknown:"


def test_preprocess_emojis_multiple_shortcodes_all_replaced():
    """Multiple shortcodes in a single text must all be resolved."""
    emoji_map = {"smile": "😄", "wave": "👋"}
    result = _preprocess_emojis("Hello :smile: world :wave:", emoji_map)
    assert "😄" in result
    assert "👋" in result
    assert ":smile:" not in result
    assert ":wave:" not in result


def test_preprocess_emojis_empty_map_preserves_all_shortcodes():
    """With an empty mapping, no shortcode must be substituted."""
    text = "Hello :smile: :wave:"
    assert _preprocess_emojis(text, {}) == text


def test_preprocess_emojis_native_unicode_emoji_untouched():
    """A native Unicode emoji 🎯 (no shortcode) must not be altered."""
    result = _preprocess_emojis("Hello 🎯 world", {"smile": "😄"})
    assert "🎯" in result


def test_preprocess_full_pipeline_does_not_alter_unrelated_content(md_file: Path):
    """_preprocess() must not modify content that has no Obsidian-specific syntax."""
    result = _preprocess(md_file)
    assert "# Hello" in result
    assert "Simple content." in result


def test_preprocess_preserves_native_emoji(md_file_with_emoji: Path):
    """_preprocess() must keep native Unicode emojis intact."""
    result = _preprocess(md_file_with_emoji)
    assert "🎯" in result
    assert "🚀" in result


def test_preprocess_replaces_emoji_shortcodes_with_json(
    md_file_with_emoji_shortcodes: Path, emoji_json: Path
):
    """_preprocess() must resolve known shortcodes using the provided JSON."""
    result = _preprocess(md_file_with_emoji_shortcodes, emoji_json=emoji_json)
    assert "😄" in result
    assert ":smile:" not in result


def test_preprocess_preserves_unknown_shortcodes_with_json(
    md_file_with_emoji_shortcodes: Path, emoji_json: Path
):
    """_preprocess() must leave shortcodes absent from the JSON unchanged."""
    result = _preprocess(md_file_with_emoji_shortcodes, emoji_json=emoji_json)
    assert ":unknown_xyz:" in result


def test_preprocess_no_emoji_substitution_when_json_is_none(
    md_file_with_emoji_shortcodes: Path,
):
    """_preprocess() with emoji_json=None must not substitute any shortcodes."""
    result = _preprocess(md_file_with_emoji_shortcodes, emoji_json=None)
    assert ":smile:" in result


def test_preprocess_table_structure_preserved(md_file_with_table: Path):
    """_preprocess() must not alter Markdown table structure."""
    result = _preprocess(md_file_with_table)
    assert "| Col A | Col B | Col C |" in result
    assert "|-------|-------|-------|" in result
    assert "| 1     | 2     | 3     |" in result


def test_preprocess_math_inline_preserved(md_file_with_math: Path):
    """_preprocess() must not alter inline LaTeX formulas ($...$)."""
    result = _preprocess(md_file_with_math)
    assert "$E = mc^2$" in result


def test_preprocess_math_block_preserved(md_file_with_math: Path):
    """_preprocess() must not alter block LaTeX formulas ($$...$$)."""
    result = _preprocess(md_file_with_math)
    assert "\\int_0^\\infty" in result


def test_preprocess_converts_wikilinks(md_file_obsidian: Path):
    """_preprocess() must convert Obsidian wikilinks to standard Markdown links."""
    result = _preprocess(md_file_obsidian)
    assert "[Other Note](Other Note.md)" in result


def test_preprocess_converts_wikilinks_with_alias(md_file_obsidian: Path):
    """_preprocess() must convert aliased wikilinks correctly."""
    result = _preprocess(md_file_obsidian)
    assert "[My Alias](Target.md)" in result


def test_preprocess_converts_embed_to_marker(md_file_obsidian: Path):
    """_preprocess() must replace ![[embed]] with a textual marker."""
    result = _preprocess(md_file_obsidian)
    assert "![[" not in result


def test_preprocess_converts_callout_icon(md_file_obsidian: Path):
    """_preprocess() must replace Obsidian callouts with their icon."""
    result = _preprocess(md_file_obsidian)
    assert "⚠️" in result


def test_preprocess_hrules_file_processed_without_error(md_file_with_hrules: Path):
    """_preprocess() must process a file containing --- separators without raising."""
    result = _preprocess(md_file_with_hrules)
    assert "# Section A" in result
    assert "# Section B" in result


# ============================================================
# 3. MAIN METHODS - to_pdf_raw / to_pdf_typst
# ============================================================

# ── to_pdf_raw ───────────────────────────────────────────────


def test_to_pdf_raw_calls_pandoc_first(mock_run_success, md_file: Path, output_pdf: Path):
    """to_pdf_raw must invoke pandoc as the first subprocess."""
    to_pdf_raw(md_file, output_pdf)
    first_cmd = mock_run_success.call_args_list[0][0][0]
    assert first_cmd[0] == "pandoc"


def test_to_pdf_raw_calls_typst_compile_second(mock_run_success, md_file: Path, output_pdf: Path):
    """to_pdf_raw must invoke typst as the second subprocess."""
    to_pdf_raw(md_file, output_pdf)
    second_cmd = mock_run_success.call_args_list[1][0][0]
    assert second_cmd[0] == "typst"


def test_to_pdf_raw_passes_typst_output_format_to_pandoc(
    mock_run_success, md_file: Path, output_pdf: Path
):
    """to_pdf_raw must pass -t typst to pandoc."""
    to_pdf_raw(md_file, output_pdf)
    pandoc_cmd = mock_run_success.call_args_list[0][0][0]
    assert "-t" in pandoc_cmd
    idx = pandoc_cmd.index("-t")
    assert pandoc_cmd[idx + 1] == "typst"


def test_to_pdf_raw_does_not_use_lualatex_engine(mock_run_success, md_file: Path, output_pdf: Path):
    """to_pdf_raw must not pass --pdf-engine=lualatex (Typst pipeline only)."""
    to_pdf_raw(md_file, output_pdf)
    for call_args in mock_run_success.call_args_list:
        assert "--pdf-engine=lualatex" not in call_args[0][0]


def test_to_pdf_raw_raises_file_not_found_when_md_missing(output_pdf: Path, tmp_path: Path):
    """to_pdf_raw must raise FileNotFoundError if the source file does not exist."""
    with pytest.raises(FileNotFoundError):
        to_pdf_raw(tmp_path / "ghost.md", output_pdf)


def test_to_pdf_raw_raises_runtime_error_on_pandoc_failure(
    mock_run_failure, md_file: Path, output_pdf: Path
):
    """to_pdf_raw must raise RuntimeError if pandoc returns a non-zero exit code."""
    with pytest.raises(RuntimeError):
        to_pdf_raw(md_file, output_pdf)


def test_to_pdf_raw_raises_on_timeout(mock_run_timeout, md_file: Path, output_pdf: Path):
    """to_pdf_raw must propagate a timeout from the subprocess."""
    with pytest.raises((RuntimeError, TimeoutExpired)):
        to_pdf_raw(md_file, output_pdf)


def test_to_pdf_raw_with_emoji_json_resolves_shortcodes(tmp_path, output_pdf, emoji_json):
    """to_pdf_raw with emoji_json must resolve shortcodes in the preprocessed file."""
    md = tmp_path / "emojis.md"
    md.write_text("# Test\n:smile:", encoding="utf-8")
    preprocessed_content = {}

    def capture(cmd, **_):
        if cmd[0] == "pandoc":
            src = next((Path(a) for a in cmd if a.endswith(".md") and Path(a).exists()), None)
            if src:
                preprocessed_content["content"] = src.read_text(encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    with (
        patch("orsync.converter.subprocess.run", side_effect=capture),
        patch("orsync.converter._fix_typst_output"),
    ):
        to_pdf_raw(md, output_pdf, emoji_json=emoji_json)

    assert "😄" in preprocessed_content.get("content", "")
    assert ":smile:" not in preprocessed_content.get("content", "")


def test_to_pdf_raw_with_emoji_json_none_does_not_raise(
    mock_run_success, md_file: Path, output_pdf: Path
):
    """to_pdf_raw with emoji_json=None must not raise."""
    to_pdf_raw(md_file, output_pdf, emoji_json=None)


def test_to_pdf_raw_missing_emoji_json_emits_user_warning(
    mock_run_success, md_file: Path, output_pdf: Path, tmp_path: Path
):
    """to_pdf_raw with a missing emoji_json path must emit a UserWarning (no exception)."""
    missing = tmp_path / "nonexistent_emojis.json"
    with pytest.warns(UserWarning, match="emojis.json"):
        to_pdf_raw(md_file, output_pdf, emoji_json=missing)


def test_to_pdf_raw_creates_output_parent_directory(
    mock_run_success, md_file: Path, tmp_path: Path
):
    """to_pdf_raw must create the output parent directory if it does not exist."""
    nested_pdf = tmp_path / "a" / "b" / "output.pdf"
    to_pdf_raw(md_file, nested_pdf)
    assert nested_pdf.parent.exists()


def test_to_pdf_raw_verbose_flag_accepted(mock_run_success, md_file: Path, output_pdf: Path):
    """to_pdf_raw must accept verbose=True without raising."""
    to_pdf_raw(md_file, output_pdf, verbose=True)


def test_run_verbose_prints_stdout_when_non_empty(md_file: Path, output_pdf: Path):
    """_run must print stdout when verbose=True and stdout is non-empty."""
    with (
        patch("orsync.converter.subprocess.run") as mock_run,
        patch("orsync.converter._fix_typst_output"),
        patch("builtins.print") as mock_print,
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="pandoc 3.1.3 compiled\n",
            stderr="",
        )
        to_pdf_raw(md_file, output_pdf, verbose=True)

    printed = [str(c.args[0]) for c in mock_print.call_args_list]
    assert any("pandoc 3.1.3" in v for v in printed)


# ── to_pdf_typst ─────────────────────────────────────────────


def test_to_pdf_typst_calls_pandoc_with_typst_output(
    mock_run_success, md_file: Path, output_pdf: Path, typ_template: Path
):
    """to_pdf_typst must invoke pandoc with -t typst."""
    to_pdf_typst(md_file, output_pdf, template=typ_template)
    pandoc_cmd = mock_run_success.call_args_list[0][0][0]
    assert "pandoc" in pandoc_cmd[0]
    assert "-t" in pandoc_cmd
    idx = pandoc_cmd.index("-t")
    assert pandoc_cmd[idx + 1] == "typst"


def test_to_pdf_typst_calls_typst_compile(
    mock_run_success, md_file: Path, output_pdf: Path, typ_template: Path
):
    """to_pdf_typst must invoke typst compile as the last subprocess."""
    to_pdf_typst(md_file, output_pdf, template=typ_template)
    last_cmd = mock_run_success.call_args_list[-1][0][0]
    assert last_cmd[0] == "typst"
    assert "compile" in last_cmd


def test_to_pdf_typst_raises_file_not_found_when_md_missing(
    output_pdf: Path, tmp_path: Path, typ_template: Path
):
    """to_pdf_typst must raise FileNotFoundError if the source file does not exist."""
    with pytest.raises(FileNotFoundError):
        to_pdf_typst(tmp_path / "ghost.md", output_pdf, template=typ_template)


def test_to_pdf_typst_raises_file_not_found_when_template_missing(
    md_file: Path, output_pdf: Path, tmp_path: Path
):
    """to_pdf_typst must raise FileNotFoundError if the Typst template does not exist."""
    with pytest.raises(FileNotFoundError, match="Template"):
        to_pdf_typst(md_file, output_pdf, template=tmp_path / "ghost.typ")


def test_to_pdf_typst_uses_default_template_when_none(
    mock_run_success, md_file: Path, output_pdf: Path, tmp_path: Path
):
    """to_pdf_typst with template=None must use default_typst_template()."""
    bundled = tmp_path / "assets" / "eink.typ"
    bundled.parent.mkdir(parents=True)
    bundled.write_text('#include "body.typ"', encoding="utf-8")

    with patch("orsync.converter.default_typst_template", return_value=bundled):
        to_pdf_typst(md_file, output_pdf, template=None)

    assert mock_run_success.called


def test_to_pdf_typst_explicit_template_does_not_call_default(
    mock_run_success, md_file: Path, output_pdf: Path, typ_template: Path
):
    """to_pdf_typst with an explicit template must not call default_typst_template()."""
    with patch("orsync.converter.default_typst_template") as mock_default:
        to_pdf_typst(md_file, output_pdf, template=typ_template)
    mock_default.assert_not_called()


def test_to_pdf_typst_raises_runtime_error_on_pandoc_failure(
    mock_run_failure, md_file: Path, output_pdf: Path, typ_template: Path
):
    """to_pdf_typst must raise RuntimeError if pandoc returns a non-zero exit code."""
    with pytest.raises(RuntimeError):
        to_pdf_typst(md_file, output_pdf, template=typ_template)


def test_to_pdf_typst_missing_emoji_json_emits_user_warning(
    mock_run_success, md_file: Path, output_pdf: Path, typ_template: Path, tmp_path: Path
):
    """to_pdf_typst with a missing emoji_json path must emit a UserWarning (no exception)."""
    missing = tmp_path / "nonexistent_emojis.json"
    with pytest.warns(UserWarning, match="emojis.json"):
        to_pdf_typst(md_file, output_pdf, template=typ_template, emoji_json=missing)


def test_to_pdf_typst_with_emoji_json_none_does_not_raise(
    mock_run_success, md_file: Path, output_pdf: Path, typ_template: Path
):
    """to_pdf_typst with emoji_json=None must not raise."""
    to_pdf_typst(md_file, output_pdf, template=typ_template, emoji_json=None)


def test_to_pdf_typst_creates_output_parent_directory(
    mock_run_success, md_file: Path, tmp_path: Path, typ_template: Path
):
    """to_pdf_typst must create the output parent directory if it does not exist."""
    nested_pdf = tmp_path / "subdir" / "nested" / "output.pdf"
    to_pdf_typst(md_file, nested_pdf, template=typ_template)
    assert nested_pdf.parent.exists()


def test_to_pdf_typst_verbose_flag_accepted(
    mock_run_success, md_file: Path, output_pdf: Path, typ_template: Path
):
    """to_pdf_typst must accept verbose=True without raising."""
    to_pdf_typst(md_file, output_pdf, template=typ_template, verbose=True)


# ============================================================
# 4. STRATEGY PATTERN
# ============================================================


def test_make_strategy_default_mode_returns_typst_strategy(
    mock_run_success, md_file: Path, output_pdf: Path, tmp_path: Path
):
    """make_strategy with no pdf_mode key must default to 'eink' (TypstStrategy)."""
    bundled = tmp_path / "assets" / "eink.typ"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("", encoding="utf-8")

    with patch("orsync.converter.default_typst_template", return_value=bundled):
        strategy = make_strategy({})

    from orsync.converter import TypstStrategy

    assert isinstance(strategy, TypstStrategy)


def test_make_strategy_raw_mode_returns_raw_strategy():
    """make_strategy with pdf_mode='raw' must return a RawStrategy."""
    from orsync.converter import RawStrategy

    strategy = make_strategy({"pdf_mode": "raw"})
    assert isinstance(strategy, RawStrategy)


def test_make_strategy_unknown_mode_raises_value_error():
    """make_strategy with an unknown pdf_mode must raise ValueError."""
    with pytest.raises(ValueError, match="Unknown PDF mode"):
        make_strategy({"pdf_mode": "latex"})


def test_make_strategy_raw_convert_invokes_to_pdf_raw(
    mock_run_success, md_file: Path, output_pdf: Path
):
    """RawStrategy.convert() must call to_pdf_raw under the hood."""
    strategy = make_strategy({"pdf_mode": "raw"})
    with patch("orsync.converter.to_pdf_raw") as mock_fn:
        strategy.convert(md_file, output_pdf)
    mock_fn.assert_called_once_with(md_file, output_pdf, emoji_json=None, verbose=False)


def test_make_strategy_eink_convert_invokes_to_pdf_typst(md_file, output_pdf):
    strategy = make_strategy({"pdf_mode": "eink"})
    with patch("orsync.converter.to_pdf_typst") as mock_fn:
        strategy.convert(md_file, output_pdf)
    mock_fn.assert_called_once()
    call_kwargs = mock_fn.call_args
    assert call_kwargs[0][0] == md_file  # src
    assert call_kwargs[0][1] == output_pdf  # dst


# ============================================================
# 5. FUNDAMENTAL BEHAVIOR & EDGE CASES
# ============================================================


def test_to_pdf_raw_and_typst_share_same_preprocessing_output(
    md_file_obsidian, output_pdf, typ_template, tmp_path
):
    """Both conversion modes must write identical preprocessed content to pandoc."""
    captured_content: dict[str, str] = {}

    def make_capture(key):
        def side_effect(cmd, **_):
            if cmd[0] == "pandoc":
                # The preprocessed .md is the first positional argument after flags
                src_path = next(
                    (Path(a) for a in cmd if a.endswith(".md") and Path(a).exists()), None
                )
                if src_path:
                    captured_content[key] = src_path.read_text(encoding="utf-8")
            return MagicMock(returncode=0, stdout="", stderr="")

        return side_effect

    with patch("orsync.converter.subprocess.run", side_effect=make_capture("raw")):
        to_pdf_raw(md_file_obsidian, output_pdf)

    output_pdf.unlink(missing_ok=True)

    with (
        patch("orsync.converter.subprocess.run", side_effect=make_capture("typst")),
        patch("orsync.converter._fix_typst_output"),
    ):
        to_pdf_typst(md_file_obsidian, output_pdf, template=typ_template)

    assert "raw" in captured_content and "typst" in captured_content
    assert (
        captured_content["raw"] == captured_content["typst"]
    ), "Both modes must preprocess wikilinks and callouts identically"


def test_preprocess_spacing_preserves_content_in_nested_fences():
    """_preprocess_spacing must not modify content inside nested code fence constructs."""
    text = "~~~\n- inner list\n~~~"
    result = _preprocess_spacing(text)
    assert "- inner list" in result


def test_fix_typst_output_replaces_horizontalrule_and_writes_file(tmp_path: Path):
    """_fix_typst_output must replace #horizontalrule and overwrite the file."""
    from orsync.converter import _fix_typst_output

    typ_file = tmp_path / "doc.typ"
    typ_file.write_text("before\n#horizontalrule\nafter", encoding="utf-8")
    _fix_typst_output(typ_file)
    content = typ_file.read_text(encoding="utf-8")
    assert "#horizontalrule" not in content
    assert "line(" in content  # the replacement snippet contains line()


def test_fix_typst_output_does_not_write_when_no_horizontalrule(tmp_path: Path):
    """_fix_typst_output must not rewrite the file if #horizontalrule is absent."""
    from orsync.converter import _fix_typst_output

    typ_file = tmp_path / "doc.typ"
    original = "no horizontalrule here"
    typ_file.write_text(original, encoding="utf-8")
    _fix_typst_output(typ_file)
    assert typ_file.read_text(encoding="utf-8") == original


def test_to_pdf_raw_unlinks_existing_doc_typ_before_pandoc(
    md_file: Path, output_pdf: Path, tmp_path: Path
):
    """to_pdf_raw must delete a pre-existing doc.typ before invoking pandoc (line 395).

    Achieved by patching TemporaryDirectory to return a controlled directory
    where doc.typ is pre-created, then verifying pandoc is still called.
    """
    # Pre-create doc.typ so the if out_typ.exists() branch is taken
    (tmp_path / "doc.typ").write_text("stale content", encoding="utf-8")

    class _FakeTmpDir:
        def __enter__(self):
            return str(tmp_path)

        def __exit__(self, *_):
            pass

    with (
        patch("orsync.converter.tempfile.TemporaryDirectory", return_value=_FakeTmpDir()),
        patch("orsync.converter.subprocess.run") as mock_run,
        patch("orsync.converter._fix_typst_output"),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        to_pdf_raw(md_file, output_pdf)

    # doc.typ was deleted then pandoc was called: the file no longer exists
    # (pandoc is mocked so it does not recreate it)
    assert not (tmp_path / "doc.typ").exists()
    assert mock_run.called


def test_to_pdf_typst_unlinks_existing_dst_and_doc_typ_before_pandoc(
    md_file: Path, tmp_path: Path, typ_template: Path
):
    """to_pdf_typst must delete a pre-existing dst PDF (line 449) and doc.typ (line 469).

    Uses the same controlled-TemporaryDirectory technique to pre-create both files.
    """
    dst = tmp_path / "output.pdf"
    dst.write_text("old pdf", encoding="utf-8")  # triggers line 449

    tmp_inner = tmp_path / "inner"
    tmp_inner.mkdir()
    (tmp_inner / "doc.typ").write_text("stale typ", encoding="utf-8")  # triggers line 469

    class _FakeTmpDir:
        def __enter__(self):
            return str(tmp_inner)

        def __exit__(self, *_):
            pass

    with (
        patch("orsync.converter.tempfile.TemporaryDirectory", return_value=_FakeTmpDir()),
        patch("orsync.converter.subprocess.run") as mock_run,
        patch("orsync.converter._fix_typst_output"),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        to_pdf_typst(md_file, dst, template=typ_template)

    # Both pre-existing files must have been deleted before pandoc ran
    assert not dst.exists()
    assert not (tmp_inner / "doc.typ").exists()
    assert mock_run.called


# ============================================================
# 6. REGRESSION & NON-REGRESSION
# ============================================================
# Empty until a bug is identified and fixed.


# ============================================================
# 7. INTEGRATION TESTS
# ============================================================


@pytest.mark.integration
def test_run_check_all_ok_is_necessary_condition_for_successful_conversion(
    md_file: Path, output_pdf: Path, typ_template: Path
):
    """run_check returning all_ok=True must be a prerequisite for conversion to succeed.

    Simulates the full setup check passing and verifies that a subsequent
    conversion call proceeds without raising a setup-related error.
    """
    from orsync.setup_check import run_check

    config = {
        "remarkable_ip_usb": "10.11.99.1",
        "remarkable_ip_wifi": "",
        "ssh_key_path": "/home/user/.ssh/id_rsa_remarkable",
        "ssh_timeout": 2,
    }

    mock_client = MagicMock()
    mock_client.exec_command.return_value = (
        MagicMock(),
        MagicMock(read=lambda: b"3.11.2.4"),
        MagicMock(),
    )

    with (
        patch("orsync.setup_check.shutil.which", return_value="/usr/bin/pandoc"),
        patch("orsync.setup_check.subprocess.run") as mock_subprocess,
        patch("orsync.setup_check._open_ssh_session") as mock_ssh,
    ):
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="pandoc 3.1\n")
        mock_ssh.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_ssh.return_value.__exit__ = MagicMock(return_value=False)
        report = run_check(config)

    assert report.all_ok is True

    # With the same tool availability, conversion must not raise a tool-related error
    with (
        patch("orsync.converter.subprocess.run") as mock_conv,
        patch("orsync.converter._fix_typst_output"),
    ):
        mock_conv.return_value = MagicMock(returncode=0, stdout="", stderr="")
        # Must not raise FileNotFoundError or EnvironmentError
        to_pdf_typst(md_file, output_pdf, template=typ_template)
