# N-Ways Addressing for Benin

**Status: issued on 20 October 2026.** Every compound in Benin has an N-Ways code: 4,147,741 of them, all published in [`registry/`](registry/), provisional until residents confirm them. Benin has no postcode. Where the State gives an address (the street codes and door numbers of Cotonou's 2013 plan today, the national programme's addresses once delivered), that address is shown first, exactly as the State writes it, with the N-Ways code beside it.

A home's code is **the name of a quartier or village people already say, and a number of four or five digits**:

| Code | Machine form | What it is |
|---|---|---|
| `Cadjéhoun · 18 07` | `BJ-COT-12-001-1807-4` | a compound in Cotonou, on Rue 12.202 (shown first) |
| `Sainte Rita · 12 403` | `BJ-COT-08-001-12403-1` | five digits, said as a pair and a hundred |
| `Agata · 15 00`, `Agata · 26 00` | `BJ-COT-06-001-1500-8`, `BJ-DAN-01-001-2600-0` | two of the three places of that name, in Cotonou and in Dangbo: one national range, three blocks |
| `COT 12 · 35G 2PX` | `BJ-COT-12-S-35G2PX` | any point: its spot code, a 3 m cell of UTM zone 31N (a point in no outline takes the nearest arrondissement within 10 km, [SPEC 2.4](engine/SPEC.md#24-points-in-no-outline)) |

The code is unique in the whole country on its own: every area with the same plate name shares one national range of numbers, cut into frozen blocks of twice its compounds, so "name · number" never needs a commune after it. People never see or type a check digit: a Damm check over the name's national index and the number is in the machine form only, for systems. The name is a **plate name** of at most 12 characters and 2 words ("Soukoumpérou" for "Camp Peulh Soukoumpérou"); the official name still finds it. 1,300 areas carry a provisional plate name that their commune may change once; their codes are issued, and their numbers never change.

## What is where

| Path | Contents |
|---|---|
| [docs/paper.md](docs/paper.md), [docs/paper.fr.md](docs/paper.fr.md) | the research paper in English and French, with the PDFs in `docs/`: the model, every formula with worked examples, the implementation, the measured evaluation, the designs compared, and what the codes change for citizens, logistics, emergency services and government. `docs/paper/` holds the LaTeX build (template, style, references) and `docs/figures/` the figure sources and their data |
| [docs/model.md](docs/model.md) | the design notes behind every choice |
| [docs/existing-systems.md](docs/existing-systems.md) | La Poste, Cotonou's 2013 plan, the national strategy of April 2026, land, data protection: what exists, with sources |
| [docs/api.md](docs/api.md) | the registry API, every endpoint with a real request and response |
| [engine/SPEC.md](engine/SPEC.md) | the engine specification (normative) |
| [engine/reference/](engine/reference/) | the reference engine (`bj_engine.py`, `plate_names.py`, standard library only), its tests (`test_bj.py`) and the conformance vectors every implementation must reproduce (`test_vectors.json`, `vectors.json`) |
| [engine/data/](engine/data/) | what a decoder ships: communes, arrondissements with their spot frames, every area with its plate and official names, name index, blocks and frame; the name table and aliases; the arrondissement outlines; the national border (`border.json`, simplified to 50 m), beyond which no Benin code is issued |
| [registry/](registry/) | every issued code, one gzip CSV per commune (`COT.csv.gz` is Cotonou), the frozen area table `areas.csv.gz`, and `MANIFEST.json` (counts and SHA-256 of every file) |
| [server/](server/) | a ready-made server and JSON API for the registry: deploy with `docker compose up` ([server/README.md](server/README.md), [server/openapi.yaml](server/openapi.yaml)) |
| [model/](model/) | `keys.json` (communes, arrondissements, code areas), `names.json` (the national name table), `units/` (arrondissement and commune outlines), `stats/` (the figures of the paper), `design.json` (every decision, machine-readable) |
| [tools/](tools/) | the scripts that built the inputs, the areas, the compounds, the names and the registry ([tools/README.md](tools/README.md)) |
| [GOVERNANCE.md](GOVERNANCE.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) | who decides, how to propose a change, how to report a problem |
| [SOURCES.md](SOURCES.md), [LICENSING.md](LICENSING.md), [NOTICE](NOTICE), [CITATION.cff](CITATION.cff) | sources, licences, credit and citation |

## Run the reference engine

Python 3.9 or newer, no packages ([requirements.txt](requirements.txt)).

```sh
python3 engine/reference/test_bj.py                               # tests
python3 engine/reference/bj_engine.py find "Cadjéhoun 18 07"      # remembered form: one area in the whole country
python3 engine/reference/bj_engine.py find "Agata 15 00, Cotonou"
python3 engine/reference/bj_engine.py find "Agata 45 00"          # refused: in the name's spare space
python3 engine/reference/bj_engine.py parse BJ-COT-12-001-1807-4  # validate a machine code
python3 engine/reference/bj_engine.py spot 6.3582212 2.3911161    # spot code: COT 12 · 35G 2PX
python3 engine/reference/bj_engine.py unspot "COT 12 · 35G 2PX"
python3 engine/reference/bj_engine.py area 6.3582212 2.3911161    # commune, arrondissement, quartier
```

## Run the server

The server serves the published registry over a JSON API: look up a code, find what people type, the code at a point, the codes nearby, spot codes, communes and areas.

```sh
cd server && docker compose up -d            # imports the registry on first start, then serves :8080
curl -s 'http://localhost:8080/v1/find?q=Cadjéhoun%2018%2007'
```

Or without Docker, from the repository root:

```sh
python3 -m server import --registry registry --db data/addresses.sqlite
python3 -m server serve --db data/addresses.sqlite --port 8080
python3 -m unittest discover -s server/tests  # tests, including parity with the N-Ways issuer
```

A deployment is read-only unless it is the designated issuer: codes for Benin are issued by one issuer only, so that no number is ever given twice ([server/README.md](server/README.md#one-issuer)).

## Build the paper

```sh
python3 tools/paper-figures.py      # the data of the figures (docs/figures/*.dat), from registry/ and model/
python3 tools/paper-evaluation.py   # the measured properties of the evaluation (model/stats/evaluation.json)
sh docs/paper/build.sh              # pandoc + tectonic (LaTeX): docs/n-ways-addressing-benin-en.pdf and -fr.pdf
```

The build needs pandoc 3, tectonic and pdftocairo. Figures are TikZ/pgfplots sources (`docs/figures/*.tex`, with `*.fr.tex` for the French labels), compiled to PDF for the paper and to SVG for the markdown.

## How the registry was made

```sh
python3 tools/prepare-inputs.py <work>              # enclosures, estates, gates, places, arrondissements, Cotonou's streets
python3 tools/extract-buildings.py <work>           # every footprint inside Benin, with its arrondissement and street
python3 tools/assign-areas.py <work>                # each footprint's code area and every area's frame
python3 tools/sort-buildings.py <work>              # sorted by area
python3 tools/issue_registry.py group <work>        # compounds and profiles, one area at a time
python3 tools/build-register.py <work> --freeze     # national ranges and blocks on the real compounds
python3 tools/issue_registry.py number <work> <work>/lotes.jsonl.gz
python3 tools/vectors.py                            # engine/reference/vectors.json
python3 tools/paper-stats.py <work> <work>/lotes.jsonl.gz
```

The N-Ways issuer then issued the codes, checking every number against the reference engine's, and exported `registry/`. The register is frozen: new compounds get new codes by the rules of `engine/SPEC.md` 5.2, and no issued code is ever renumbered.

## Licence and credit

Code (engine, tools, server): Apache License 2.0, with [NOTICE](NOTICE). Data (registry, model, engine data): ODbL 1.0. Documents: CC BY 4.0. Credit every use: **"N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"**, with a link to this repository ([LICENSING.md](LICENSING.md)). Derived from OpenStreetMap (© OpenStreetMap contributors, ODbL), Google Open Buildings (CC BY 4.0), Microsoft building footprints (ODbL), geoBoundaries (ODbL) and OCHA's commune boundaries (CC BY-IGO).
