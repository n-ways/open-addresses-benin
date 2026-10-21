# Licensing

N-Ways Addressing for Benin is open. Build on it, and credit N-Ways.

| Part | Licence | File |
|---|---|---|
| Code: the engine, the tools and the server (`engine/reference/`, its test vectors, `tools/`, `server/` with its OpenAPI description and tests) | Apache License 2.0 | [LICENSE](LICENSE), [NOTICE](NOTICE) |
| Data: the registry, doors, areas, the national outline and model (`registry/`, `doors/`, `model/`, `engine/data/`, and the registry extract in `server/testdata/`) | Open Database License (ODbL) 1.0 | [LICENSE-DATA](LICENSE-DATA) |
| Documents: the research paper, the design notes, the verification of existing systems and the API reference (`docs/`), and this repository's other Markdown files | Creative Commons Attribution 4.0 (CC BY 4.0) | [LICENSE-DOCS](LICENSE-DOCS) |

Licensor: **N-WAYS LIMITED** (nways.ng). Source: https://github.com/n-ways/open-addresses-benin

## How to credit N-Ways

Copy the line that fits. Link it to https://github.com/n-ways/open-addresses-benin where you can.

**An app, a website or an API that shows, decodes or issues these addresses** (a deployment of `server/` included):

> Codes by N-Ways Addressing · © N-WAYS LIMITED (nways.ng)

Put it next to the address, or on the screen that shows it, and in your about or licences screen. If you ship or change the engine, also keep [NOTICE](NOTICE) (Apache 2.0, section 4(d)).

**A map, a dataset or a database built from the data:**

> © N-WAYS LIMITED, N-Ways Addressing; contains OpenStreetMap data © OpenStreetMap contributors (ODbL) and the other sources in SOURCES.md

A database you make from it and share is shared under ODbL 1.0 too (share-alike). A map image or a printed plate made from it is a "produced work": it carries the line above, and needs no share-alike.

**A paper, an article, a slide or a translation that uses the documents** (citation metadata in [CITATION.cff](CITATION.cff)):

> N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng), CC BY 4.0. https://github.com/n-ways/open-addresses-benin

Say what you changed, if you changed anything.

## Sources inside the data

The data is built from open sources (full list in [SOURCES.md](SOURCES.md)). Their own terms travel with it, and the data credit above names them:

| Source | Licence | What you owe it |
|---|---|---|
| OpenStreetMap (buildings, places, gates and enclosures derived from it) | ODbL 1.0 | "© OpenStreetMap contributors"; share-alike, which is why the data is ODbL |
| Microsoft building footprints, via Overture Maps | ODbL 1.0 | credit Microsoft and the Overture Maps Foundation |
| Google Open Buildings, via Overture Maps | CC BY 4.0 | credit Google and the Overture Maps Foundation; compatible with redistribution inside an ODbL database |
| OpenStreetMap: the national boundary, Cotonou's named and coded streets and the place nodes the code areas are named after | ODbL 1.0 | "© OpenStreetMap contributors" |
| Arrondissement boundaries (geoBoundaries BEN ADM3, 2021) | ODbL 1.0 | credit geoBoundaries |
| Commune boundaries (OCHA COD-AB Benin) | CC BY-IGO 3.0 | credit OCHA and the source on HDX |
| N-Ways places (used only to classify buildings: OSM, Overture, Foursquare OS Places, All The Places) | per source (ODbL, CDLA-Permissive-2.0, Apache-2.0, CC0) | only categories are used, no place records are redistributed |

**Postcodes.** Benin has no postcode; none is in this repository. P.O. boxes of La Poste du Bénin are not addresses and are not in it either.

**Official addresses.** In Cotonou the 2013 addressing plan is official: the official street is shown first, and a door number of the plan, once known for a gate, replaces it (engine/SPEC.md section 1a); the national programme's addresses, once delivered, come first in its towns. The State's own datasets keep their own terms; the registry carries the official address text shown with each code (in Cotonou, the coded street as it appears in OpenStreetMap). Both licences above let the State relicense or republish the registry if it adopts it.

**Personal data.** The registry holds places, never people (docs/paper.md, Privacy).

## Trademarks

"N-Ways" and the N-Ways logo are trade marks of N-WAYS LIMITED. The licences above cover the code, data and documents, not the marks: you may say your product uses N-Ways Addressing, but not that it is N-Ways or is endorsed by N-Ways.
