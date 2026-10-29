# Paper — PNAS LaTeX scaffold

Scaffold for the paper "Do LLMs Replicate Human Behavioural Treatment Effects?
Direction, Magnitude, and the Limits of Language-Model Simulacra". All text is
TODO placeholders; the user writes the prose.

## File layout

- `main.tex` — top-level file: class, metadata, abstract, inputs of the
  section files, placeholder figure/table, bibliography hooks.
- `sections/introduction.tex`, `sections/results.tex`,
  `sections/discussion.tex`, `sections/methods.tex` — empty comment-only
  stubs; write prose here.
- `references.bib` — bibliography; entries marked `% TODO` have unverified
  metadata and must be checked against the original sources.
- `figures/` — figures (empty).
- `pnas-new.cls`, `pnasresearcharticle.sty`, `pnas-new.bst`, `widetext.sty`
  — official PNAS class files. Do not modify.

## Compile

`latexmk` is not installed. Run:

```
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

(all with `-interaction=nonstopmode` if run from a script). Output: `main.pdf`.

## Provenance

Class files come from github.com/dereckmezquita/latex-template-pnas, a mirror
of the official NAS/Overleaf PNAS 2025 research-report template. A pristine
copy of the mirror is kept in `vendor/` for reference (see `vendor/main.tex`
for the full macro boilerplate).

## TODO

- Replace all TODO placeholders in `main.tex` (authors, affiliations,
  significance statement, keywords, abstract, corresponding author).
- Write prose in the four `sections/*.tex` files.
- Replace the placeholder figure and table.
- Verify every `% TODO`-marked entry in `references.bib` against the
  original sources.
