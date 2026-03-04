// ─────────────────────────────────────────────────────────────────────────────
// Zephyr Pin Configurator — Shared Document Template
// ─────────────────────────────────────────────────────────────────────────────

// ── Color palette (Catppuccin Mocha-inspired) ────────────────────────────────
#let accent  = rgb("#89b4fa")
#let subtext = rgb("#a6adc8")
#let green   = rgb("#a6e3a1")
#let red     = rgb("#f38ba8")
#let yellow  = rgb("#f9e2af")

// ── Reusable page template ──────────────────────────────────────────────────
#let enterprise-doc(
  title: "",
  subtitle: "",
  version: "0.1.0",
  date: datetime.today(),
  doc,
) = {
  set document(
    title: title + " — " + subtitle,
    author: ("Pyontrust Contributors",),
    date: date,
  )

  set page(
    paper: "a4",
    margin: (top: 3cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm),
    header: context {
      if counter(page).get().first() > 1 [
        #set text(8pt, fill: luma(120))
        #subtitle — #title #h(1fr) v#version
        #line(length: 100%, stroke: 0.4pt + luma(200))
      ]
    },
    footer: context {
      set text(8pt, fill: luma(120))
      line(length: 100%, stroke: 0.4pt + luma(200))
      v(4pt)
      [Pyontrust — Confidential #h(1fr) Page #counter(page).display("1 / 1", both: true)]
    },
  )

  set text(font: "New Computer Modern", size: 10.5pt)
  set par(justify: true, leading: 0.65em)
  set heading(numbering: "1.1.1")

  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    v(1.5em)
    block(text(16pt, weight: "bold", fill: accent, it))
    v(0.6em)
  }

  show heading.where(level: 2): it => {
    v(1em)
    block(text(13pt, weight: "bold", it))
    v(0.4em)
  }

  show heading.where(level: 3): it => {
    v(0.8em)
    block(text(11pt, weight: "bold", it))
    v(0.3em)
  }

  show raw.where(block: false): box.with(
    fill: luma(240),
    inset: (x: 3pt, y: 0pt),
    outset: (y: 3pt),
    radius: 2pt,
  )

  show raw.where(block: true): block.with(
    fill: luma(245),
    inset: 10pt,
    radius: 4pt,
    width: 100%,
  )

  // ── Title page ──────────────────────────────────────────────────────────
  page(header: none, footer: none)[
    #align(center + horizon)[
      #block(width: 80%)[
        #v(2em)
        #text(28pt, weight: "bold", fill: accent)[#title]
        #v(0.3em)
        #text(14pt, fill: subtext)[#subtitle]
        #v(2em)
        #line(length: 50%, stroke: 1pt + accent)
        #v(2em)
        #text(11pt)[
          *Version* #version \
          *Date* #date.display("[month repr:long] [day], [year]") \
          *License* Apache-2.0
        ]
        #v(4em)
        #text(9pt, fill: luma(140))[
          © 2024–2026 Pyontrust Contributors
        ]
      ]
    ]
  ]

  // ── Table of contents ──────────────────────────────────────────────────
  page(header: none)[
    #v(2em)
    #text(18pt, weight: "bold", fill: accent)[Contents]
    #v(1em)
    #outline(indent: 1.5em, depth: 3)
  ]

  doc
}

// ── Helper: API parameter table ─────────────────────────────────────────────
#let param-table(..rows) = {
  let data = rows.pos()
  table(
    columns: (auto, auto, auto, auto, 1fr),
    stroke: 0.5pt + luma(200),
    inset: 6pt,
    [*Name*], [*In*], [*Type*], [*Required*], [*Description*],
    ..data.flatten(),
  )
}

// ── Helper: note/warning callout ────────────────────────────────────────────
#let note(body) = {
  block(
    fill: rgb("#e8f4fd"),
    inset: 12pt,
    radius: 4pt,
    width: 100%,
  )[
    #text(weight: "bold")[ℹ Note:] #body
  ]
}

#let warning(body) = {
  block(
    fill: rgb("#fff8e1"),
    inset: 12pt,
    radius: 4pt,
    width: 100%,
  )[
    #text(weight: "bold")[⚠ Warning:] #body
  ]
}

#let tip(body) = {
  block(
    fill: rgb("#e8f5e9"),
    inset: 12pt,
    radius: 4pt,
    width: 100%,
  )[
    #text(weight: "bold")[💡 Tip:] #body
  ]
}
