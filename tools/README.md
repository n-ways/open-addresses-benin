# Tools: how Benin's registry was built

All inputs are read-only: the N-Ways map data (`NWAYS_ROOT`) and the N-Ways map database (`NWAYS_DB`, tables `regions` and `places`). Outside N-Ways, start from the published `registry/` and `model/` instead. Run one heavy step at a time: DuckDB runs with `memory_limit='3GB'` and spills to the work folder; the grouping reads the footprints one code area at a time.

| Step | Script | Writes |
|---|---|---|
| 1 | osmium exports (below) | `admin`, `bar`, `place`, `hw` `.geojsonseq` in the work folder |
| 2 | `prepare-inputs.py <work>` | `units.geojson` (the 546 arrondissements), `streets.csv` (the named streets of Cotonou, with the codes of the 2013 plan), `enclosures.geojson`, `estates.geojson`, `gates.csv`, `places.csv`, `country.geojson` |
| 2a | `country-border.py <work>` | `engine/data/border.json`: the national border of `country.geojson` simplified to 50 m (both directions checked), for the server and decoders |
| 3 | `extract-buildings.py <work>` | `buildings-raw.csv` (every footprint whose centre is inside the national border, with its enclosure, estate, unit and nearest official street within 30 m), `buildings-pts.csv` (centre, unit, density), `enclosure-gates.csv` |
| 4 | `assign-areas.py <work>` | `area-of.csv` (each footprint's code area: the nearest named place of its arrondissement), `area-boxes.json` (each area's frame) |
| 5 | `sort-buildings.py <work>` | `buildings.csv`, sorted by area |
| 6 | `issue_registry.py group <work>` | `compounds.jsonl.gz` (compounds and profiles, none more than 300 m outside the national border; huts clustered only in rural Alibori, Atacora, Borgou and Collines), `area-counts.json`, `group-stats.json` |
| 7 | `build-register.py <work> --freeze` | plate names, national ranges and blocks on the real compounds (`name_ranges.py`): `model/names.json`, `engine/data/register.json`, `engine/data/units.json`, `model/stats/register.json` |
| 8 | `issue_registry.py number <work> <work>/lotes.jsonl.gz` | the lotes, area by area, with the reference's numbers and Cotonou's official street |
| 9 | the N-Ways issuer: issues the lotes of `<work>/lotes.jsonl.gz`, then exports the register | the codes, after checking every number against the reference's; the registry, gzipped into `registry/` (the same format as `python3 -m server export`) |
| 10 | `vectors.py`, `paper-stats.py <work> <work>/lotes.jsonl.gz` | `engine/reference/vectors.json`, `model/stats/building-stats.json` |
| 11 | `paper-figures.py`, `paper-evaluation.py` (from the published `registry/` and `model/` only) | `docs/figures/*.dat` (the data of the paper's figures), `model/stats/evaluation.json` (uniqueness, lengths, decoding, transcription errors, spot codes) |

### The border decides

A Benin code is only ever issued for a building whose entrance lies inside Benin's national border, the OpenStreetMap `boundary=administrative` `admin_level=2` relation of the extract (written to `country.geojson` by step 2), or within 300 m of it (`engine/SPEC.md` 1b). The arrondissement outlines (geoBoundaries) and the spot frames reach over the border in places; they never decide. Three steps enforce it, so a re-run on other inputs cannot code a building in a neighbouring country:

- step 3 keeps only footprints whose centre lies inside the border (stricter than 300 m);
- step 6 drops any compound whose point lies more than 300 m outside it (`abroad` in `group-stats.json`; 0 on the N-Ways inputs);
- the server and the N-Ways issuer refuse a new code or an entrance more than 300 m outside it (`422 outside_country`), using `engine/data/border.json` from step 2a and `engine/reference/bj_border.py`.

Check a registry against the border with `bj_border.Border.load('<work>/country.geojson')` and `outside_m(lat, lon)` on every `entrance_lat`, `entrance_lng`: the published registry has 0 codes outside the border.

`bj_plates.py` holds Benin's plate-name rules; `build_keys.py` built the communes, arrondissements and code areas (`model/keys.json`); `make_vectors.py` writes the design vectors (`engine/reference/test_vectors.json`) from the frozen blocks. The statistics scripts of the design (`stats.py`, `analyse.py`, `places-areas.py`, `national-areas.py`) are kept for the record.

### osmium exports

```
P=data/osm/benin-latest.osm.pbf
osmium tags-filter -o b.osm.pbf $P r/boundary=administrative
osmium export -a type,id -f geojsonseq --geometry-types=polygon -o admin.geojsonseq b.osm.pbf
osmium tags-filter -o bar.osm.pbf $P w/barrier=wall,fence,hedge,retaining_wall n/barrier=gate,entrance,lift_gate,sliding_gate,swing_gate n/entrance
osmium export -a type,id -f geojsonseq -o bar.geojsonseq bar.osm.pbf
osmium tags-filter -o place.osm.pbf $P n/place
osmium export -a type,id -f geojsonseq -o place.geojsonseq place.osm.pbf
osmium tags-filter -o hw.osm.pbf $P w/highway
osmium export -a type,id -f geojsonseq -o hw.geojsonseq hw.osm.pbf
```
