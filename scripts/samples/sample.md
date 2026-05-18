# Sample Note - Converter Rendering Check

This document is used to visually validate the rendering of `converter.py` in both `raw` and `eink` modes. It covers the full range of Markdown constructs supported by the Pandoc -> Typst pipeline.

---

## 1. Text Formatting

This is a standard paragraph. It contains **bold text**, *italic text*, ~~strikethrough~~, and `inline code`. Combinations are also tested: ***bold and italic***, and `inline code` adjacent to **bold**.

Here is a second paragraph, separated by a blank line. Paragraph spacing is one of the key readability criteria on an e-ink screen - it should be visible but not excessive.

---

## 2. Headings at Every Level

### Level 3 - Section heading

#### Level 4 - Subsection heading

##### Level 5 - Minor heading

---

## 3. Emojis

Emojis embedded directly in Unicode are supported in both modes. Shortcode substitution (`: rocket :` -> 🚀) is handled by the Python preprocessor using `assets/emojis.json` before Pandoc is invoked.

| Emoji | Shortcode | Expected in raw | Expected in eink |
|-------|-----------|-----------------|------------------|
| ✅ | `white_check_mark` | dropped | rendered |
| ❌ | `x` | dropped | rendered |
| 📝 | `memo` | dropped | rendered |
| 🚀 | `rocket` | dropped | rendered |
| ⚠️ | `warning` | dropped | rendered |
| 🎯 | `dart` | dropped | rendered |
| 💡 | `bulb` | dropped | rendered |
| 🔥 | `fire` | dropped | rendered |

A line with mixed content: **Status** ✅ done - **Risk** ⚠️ medium - **Priority** 🎯 high.

---

## 4. Obsidian Callouts

Callouts are converted by `_preprocess_callouts()` before Pandoc sees the file. Each `[!type]` block becomes a rich blockquote with an icon.

> [!note] About this pipeline
> The conversion chain is: Python preprocessing -> Pandoc (Markdown -> Typst) -> Typst compile -> PDF.

> [!warning] SSH connection required
> The `sync` command requires an active SSH connection to the reMarkable tablet. Run `setup_check.py` first.

> [!tip]
> Use `--verbose` to display the full Pandoc and Typst logs during conversion.

> [!success] Template loaded
> `assets/eink.typ` was found and will be applied in `eink` mode.

---

## 5. Wikilinks

Wikilinks are resolved by `_preprocess_wikilinks()`. The three forms below are all handled before Pandoc is invoked:

- Simple link: `[[My Other Note]]` -> rendered as `[My Other Note](My Other Note.md)`
- Aliased link: `[[My Other Note|See here]]` -> rendered as `[See here](My Other Note.md)`
- Embed: `![[diagram.png]]` -> replaced with an italic text marker *(embed: diagram.png)*

Unresolved links (target not found in the vault index) are rendered as plain text by `vault.py`.

---

## 6. Lists

### Unordered list

- First item at level 1
- Second item at level 1
    - Nested item at level 2
    - Another nested item
        - Deep nesting at level 3
- Back to level 1

### Ordered list

1. First step
2. Second step
3. Third step
    1. Sub-step A
    2. Sub-step B
4. Fourth step

### Task list (Obsidian-style)

- [ ] Pending task
- [x] Completed task
- [ ] Another pending task with **bold** text and an emoji 📌

---

## 7. Code Blocks

Inline code: `vault_path = Path("/home/user/obsidian")`.

Python block:

```python
from pathlib import Path
from orsync.converter import to_pdf_typst

md_path = Path("notes/my_note.md")
output_path = Path("/tmp/my_note.pdf")

to_pdf_typst(md_path, output_path)
print(f"Generated: {output_path}")
```

Shell block:

```bash
python scripts/check_converter.py --mode eink --verbose
python scripts/check_converter.py --mode raw --no-open
```

YAML block (example `config.yaml`):

```yaml
vault_path: /home/user/obsidian
remarkable_ip_usb: 10.11.99.1
remarkable_ip_wifi: 192.168.1.42
ssh_key_path: ~/.ssh/id_rsa_remarkable
ssh_timeout: 5
pdf_mode: eink
verbose: false
```

---

## 8. Blockquotes

> This is a simple blockquote. It should be visually indented and distinguishable from body text.

> Multi-line blockquote.
> The second line continues the same quote block.
> This is particularly relevant for bibliography entries and citation rendering.

---

## 9. Tables

| Module | Responsibility | Target coverage |
|---|---|---|
| `setup_check.py` | Verify dependencies and SSH connections | ≥ 90 % |
| `vault.py` | Scan vault, resolve wikilinks | ≥ 90 % |
| `converter.py` | Pre-process and convert `.md` to PDF | ≥ 90 % |
| `sync_engine.py` | Hash comparison and annotation decisions | **100 %** |
| `remarkable.py` | SSH push to reMarkable tablet | ≥ 90 % |
| `puller.py` | Pull annotated notebooks from tablet | ≥ 90 % |

---

## 10. Horizontal Rules and Spacing

Section separator above. The horizontal rule (`---`) is intercepted by `_preprocess_hrules()` and replaced with `<hr>` to avoid ambiguity in the Pandoc + Typst pipeline. Spacing above and below should be consistent across modes.

---

## 11. Links

- External link: [Pandoc documentation](https://pandoc.org)
- External link: [Typst](https://typst.app)
- External link: [reMarkable developer resources](https://remarkable.com)
- Wikilink (Obsidian-style, shown as code): `[[My Other Note]]`

In `eink` mode, links render as coloured underlined text via Typst. In `raw` mode, rendering depends on the default Typst output.

---

## 12. Long Paragraph - Line Length and Wrapping

This paragraph is intentionally long to verify that line length and wrapping behave correctly on both A4 (`raw` mode) and A5 (`eink` mode) page sizes. The reMarkable 2 screen is closer to A5 in proportions, so the `eink` Typst template targets A5 with 20 mm margins - approximately 105 mm of usable text width. At 14 pt, this fits around 60 characters per line, which is comfortable for sustained reading on an e-ink display. This sentence continues to ensure the paragraph is long enough to trigger multiple line wraps and confirm that `--wrap=none` in the Pandoc call does not cause overflow issues.

---

## 13. Mathematical Formulas

### Inline formula

Newton's second law in inline form: the net force is $F = ma$, where $m$ is the mass (kg) and $a$ the acceleration (m/s²).

### Block formula - Newton's laws of motion

The three laws can be expressed compactly. The second law in its general (variable mass) form is:

$$
\vec{F} = \frac{d\vec{p}}{dt} = \frac{d(m\vec{v})}{dt}
$$

For constant mass, this reduces to the familiar $\vec{F} = m\vec{a}$.

The work-energy theorem follows directly by integrating over displacement:

$$
W = \int_{\vec{r}_1}^{\vec{r}_2} \vec{F} \cdot d\vec{r} = \Delta E_k = \frac{1}{2}m v_2^2 - \frac{1}{2}m v_1^2
$$

with:
- $\vec{F}$ : net force vector (N)
- $m$ : mass of the body (kg)
- $\vec{v}$ : velocity vector (m/s)
- $\vec{p} = m\vec{v}$ : linear momentum (kg·m/s)
- $W$ : work done by the net force (J)

### Block formula - Rotation matrix

A 3D rotation around the $z$-axis by angle $\theta$ is represented by:

$$
R_z(\theta) =
\begin{bmatrix}
\cos\theta  & -\sin\theta & 0 \\
\sin\theta  &  \cos\theta & 0 \\
0           &  0          & 1
\end{bmatrix}
$$

with:
- $\theta$ : rotation angle (rad)
- $R_z \in SO(3)$ : special orthogonal group, $R_z^{\top} R_z = I$, $\det(R_z) = 1$

---

## 14. Citation (Bibliography)

This synchronisation pipeline is inspired by the following approach:

> Doe, J., & Smith, A. (2023). *Offline synchronisation of handwritten annotations with structured document pipelines*. Journal of Personal Knowledge Management, 4(2), 112-130. https://doi.org/10.xxxx/jpkm.2023.0412

Citations render with the same indentation as a standard blockquote. In `eink` mode, the DOI link is rendered as coloured underlined text by Typst.

---

*End of document - Generated by `scripts/check_converter.py`*