# aureport — LaTeX / Overleaf template for the Data Visualization course project report

The LaTeX counterpart of the Typst template in `../typst-au-report`, with the same look: a
full-bleed photo cover in AU blue with a slanted cut, section name and page number in the
header, blue sans-serif headings, booktabs tables, author–year (APA) citations and lettered
appendices.

```
overleaf-au-report/
├── aureport.cls     the document class (XeLaTeX / LuaLaTeX)
├── main.tex         the report skeleton: guideline sections with page budgets in comments
├── references.bib   two example entries
├── latexmkrc        local build configuration (xelatex + biber)
├── figures/         auseal_white.png (the AU seal), cover.png (placeholder — replace it)
└── fonts/           AU Passata (regular, bold) for the headings
```

## Using it on Overleaf

1. Zip this folder (`zip -r overleaf-au-report.zip overleaf-au-report`) and upload it with
   *New Project → Upload Project*.
2. In the Overleaf menu set **Compiler: XeLaTeX** (the class uses `fontspec`; LuaLaTeX also works).
   The bibliography runs through biber automatically.
3. Edit `main.tex`: `\title`, `\author{A \and B \and C}` (one `\and` between team members),
   `\affiliation`, `\date`, and replace `figures/cover.png` with your own photo (any aspect
   ratio; it is scaled to cover the bottom band and cropped). Leave `\coverimage{}` empty for a
   solid-colour cover.

## Building locally

```sh
latexmk            # uses latexmkrc: xelatex + biber
latexmk -C         # clean
```

Fonts: headings use AU Passata from `fonts/` (loaded by file, so nothing needs installing);
the body uses Libertinus Serif if it is installed or shipped by your TeX distribution
(`libertinus-otf`), and falls back to Latin Modern otherwise. The bibliography uses
`biblatex` with `style=apa` when `biblatex-apa` is installed (it is on Overleaf) and the built-in
`authoryear` style otherwise; cite with `\parencite{key}` → (Author, 2020) and `\textcite{key}` → Author (2020).

## What the class provides

| Command | Meaning |
|---|---|
| `\category{…}` | The small line above the title on the cover |
| `\title{…}`, `\author{A \and B}`, `\date{…}` | As usual; every `\and` starts a new line on the cover |
| `\affiliation{…}` | Printed under the authors |
| `\logo{\includegraphics[width=3.4cm]{…}}` | Top-right of the cover (use the white seal) |
| `\coverimage{figures/photo.png}` | Photo along the bottom of the cover; empty = solid cover |
| `\makecover` | Draws the cover and resets the page counter |
| `\sectionrow{n}{Title}` | A grey section row spanning `n` columns of a booktabs table |
| `\appendix` | Lettered sections and `A1, A2, …` figure/table numbers, plus an "Appendices" heading |
| column types `L{width}`, `Y` | Ragged-right fixed-width / stretch columns for `tabularx` |

The cut geometry of the cover (`\aur@cutleft`, `\aur@cutright`, `\aur@imagetop`) matches
`cover.typ` in the Typst package; change the three numbers in `aureport.cls` to move the edge.

## Licence

MIT. AU Passata is Aarhus University's brand font and is included for use in AU course work.
