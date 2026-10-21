#!/bin/sh
# Builds the paper's PDFs from docs/paper.md and its translation docs/paper.fr.md with pandoc and LaTeX (tectonic).
#   sh docs/paper/build.sh
# Needs pandoc 3, tectonic and pdftocairo. The figures are compiled first from docs/figures/*.tex (their data,
# docs/figures/*.dat, is written by tools/paper-figures.py): PDF for the paper, SVG for the markdown.
set -e
here=$(cd "$(dirname "$0")" && pwd)
docs=$(dirname "$here")
for f in "$docs"/figures/*.tex; do
  [ -e "$f" ] || continue
  b=${f%.tex}
  src=${b%.fr}
  # rebuilt when the figure, its English source (for x.fr.tex), the shared settings or any data file is newer
  stale=0
  [ -e "$b.pdf" ] || stale=1
  for dep in "$f" "$src.tex" "$docs"/figures/common.tikz "$docs"/figures/*.dat; do
    [ -e "$dep" ] && [ "$dep" -nt "$b.pdf" ] && stale=1
  done
  if [ $stale = 1 ]; then
    (cd "$docs/figures" && tectonic -X compile "$(basename "$f")" 2>&1 | grep -v "^note:\|^warning: accessing absolute path" || true)
    pdftocairo -svg "$b.pdf" "$b.svg"
  fi
done
build() { # $1 source, $2 output
  pandoc "$docs/$1" --from markdown+tex_math_dollars+raw_tex --template "$here/template.tex" \
    --lua-filter "$here/figures.lua" --citeproc --bibliography "$here/references.bib" --csl "$here/ieee.csl" \
    -H "$here/style.tex" -H "$here/colours.tex" --resource-path "$docs:$here" --number-sections --toc --pdf-engine=tectonic -o "$docs/$2"
}
base=n-ways-addressing-benin
for src in "$docs"/paper.md "$docs"/paper.*.md; do
  [ -e "$src" ] || continue
  name=$(basename "$src")
  case $name in paper.md) lang=en ;; *) lang=${name#paper.}; lang=${lang%.md} ;; esac
  build "$name" "$base-$lang.pdf"
done
