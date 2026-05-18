// ============================================================
// PAGE CONFIGURATION
// ============================================================
#set page(
  paper: "a5",
  margin: (top: 20mm, bottom: 20mm, left: 18mm, right: 18mm),
  numbering: "1",
  number-align: center + bottom,
)

// ============================================================
// TYPOGRAPHY
// ============================================================
#set text(
  font: ("Georgia", "Times New Roman", "Cambria"),
  size: 11pt,
  lang: "fr",
)

#set par(
  justify: false,
  leading: 0.75em,
  spacing: 1.2em,
)

// ============================================================
// STYLES
// ============================================================
#show heading.where(level: 1): it => {
  v(1.5em)
  text(size: 17pt, weight: "bold", fill: rgb("#111111"), it.body)
  v(0.6em)
  line(length: 100%, stroke: 0.5pt + rgb("#555555"))
  v(0.4em)
}

#show heading.where(level: 2): it => {
  v(1.2em)
  text(size: 14pt, weight: "bold", fill: rgb("#222222"), it.body)
  v(0.3em)
}

#show heading.where(level: 3): it => {
  v(1em)
  text(size: 12pt, weight: "bold", fill: rgb("#333333"), it.body)
  v(0.2em)
}

#show heading.where(level: 4): it => {
  v(0.8em)
  text(size: 11pt, weight: "bold", fill: rgb("#444444"), it.body)
  v(0.1em)
}

#show heading.where(level: 5): it => {
  v(0.6em)
  text(size: 10pt, weight: "bold", style: "italic", fill: rgb("#555555"), it.body)
}

// ============================================================
// CODE
// ============================================================
#show raw.where(block: false): it => {
  box(
    fill: rgb("#f0f0f0"),
    inset: (x: 3pt, y: 1pt),
    radius: 2pt,
    text(font: ("Consolas", "Courier New"),
         fill: rgb("#333333"),
         it)
  )
}

#show raw.where(block: true): it => {
  block(
    width: 100%,
    fill: rgb("#f5f5f5"),
    stroke: 0.4pt + rgb("#cccccc"),
    inset: 10pt,
    radius: 4pt,
    text(font: ("Courier New", "Consolas"),
         size: 9pt,
         fill: rgb("#1a1a1a"),
         it)
  )
}

// ============================================================
// TABLES
// ============================================================
#set table(
  stroke: 0.5pt + rgb("#aaaaaa"),
  inset: 6pt,
  align: left,
)

#show table.header: set text(weight: "bold", fill: rgb("#111111"))

// ============================================================
// BLOCKQUOTES
// ============================================================
#show quote: it => {
  pad(left: 14pt,
    block(
      stroke: (left: 3pt + rgb("#888888")),
      inset: (left: 10pt, y: 4pt),
      text(fill: rgb("#444444"), style: "italic", it.body)
    )
  )
}

// ============================================================
// LINKS
// ============================================================
#show link: it => {
  text(fill: rgb("#1a5fa8"), underline(it))
}

// ============================================================
$body$
