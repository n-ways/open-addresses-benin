# Benin address engine: specification

Issued on 20 October 2026: one code for every compound in Benin, frozen in `engine/data/register.json` and published in `registry/`. This engine is for Benin only. Reference implementation: [reference/bj_engine.py](reference/bj_engine.py) (Python standard library). Test vectors: [reference/test_vectors.json](reference/test_vectors.json) and [reference/vectors.json](reference/vectors.json) (from the frozen register, `tools/vectors.py`). Tests: `python3 engine/reference/test_bj.py`.

The key words MUST, SHOULD and MAY are used as in RFC 2119.

## 1. Data files

| File | Content | Licence of source |
|---|---|---|
| `model/keys.json` | 77 communes (key, name, département); 546 arrondissements: id, commune key, number, name, area, structures, UTM frame (`e0`, `n0`, `kx`, `ky`), digits, and code areas (`places`: name = official name, kind, lon, lat, index; `plate` where the plate name differs, `plateRule`, `needsCouncilChoice`, `plateCandidates`, `plateReason`, section 7.2). An arrondissement with no place carries the plate fields of its area 000 | derived; places from OSM (ODbL) |
| `model/names.json` | national name table: per normalised plate name its spelling `p`, index, digit count and frozen blocks `[area key, first number, size]` (10,841 names, 12,964 blocks); `aliases` (normalised official name → plate name, 1,109) and `aliasesDropped` (5). Built by `tools/name_ranges.py`; counts in `model/stats/name-ranges.json` | derived |
| `model/units/arrondissements.geojson` | arrondissement outlines, simplified to about 40 m | geoBoundaries BEN ADM3 2021 (ODbL) |
| `model/units/communes.geojson` | commune outlines | OCHA COD-AB (CC BY-IGO) |
| `engine/data/register.json`, `engine/data/units.json` | what a decoder ships: communes, arrondissements with their spot frames, every area with its plate and official names, name index, digits, blocks (first and last number), numbering frame and place point; the name table and aliases; the arrondissement outlines | derived |
| `registry/<COMMUNE>.csv.gz`, `registry/areas.csv.gz`, `registry/MANIFEST.json` | every issued code, one file per commune, the frozen area table, counts and SHA-256 | ODbL |
| `engine/data/border.json` | Benin's national border (OpenStreetMap relation 192784, `admin_level=2`), simplified to 50 m (`toleranceM`; 3,274 of 20,584 vertices, 67 kB), read by `reference/bj_border.py` (section 1b). Built by `tools/country-border.py` | OSM (ODbL) |
| `doors/` | confirmed entrances, added as people confirm them (empty until the first confirmations) | ODbL |

Offline, an app needs `keys.json` (1.5 MB with plate names, or 0.2 MB without places) and the outlines (0.5 MB) to compute spot codes and code areas, and `names.json` (1.1 MB with aliases, about 0.2 MB gzipped) to decode any remembered code in Benin. To show compound codes, it needs the registry slice of its commune (Cotonou ≈ 110,000 compounds ≈ 8 MB as compact JSON, about 2 MB gzipped).

## 1a. Official addresses first (import)

Where the State gives a door or street address, the engine uses it and shows it first, exactly as written: an official address is the one people should see. Every compound also has its N-Ways code, shown beside the official address and never in its place, because official addresses cover part of Cotonou only, can be incomplete (a street without a door number) and can change, while a code that every compound has in the same form is what lets any service reach any home.

**Sources:**

- **Cotonou's 2013 plan** (Commune of Cotonou, addressing cell): street code `<arr>.<street 3d>` and metric door number. The dataset is not open and is to be obtained through a data-sharing agreement.
- **Until then:**
  - OSM highway `ref`/`name` values matching `\b\d{1,2}\.\d{1,3}\b` (307 in central Cotonou);
  - door numbers read from plates by people at door confirmation, accepted after two independent readings that agree.
- **Later:** the national programme of 22 Apr 2026, once it delivers addresses.

**Import rules:**

- An official address is attached to the entrance it names, and so to that entrance's compound. Its text MUST be stored and shown exactly as written (`N° 43, Rue 12.217`), with authority, source and `syncedAt`.
- In Cotonou, before any door number is known, the official street within 30 m of the compound (OSM name and the 2013 code, `Rue 12.217, Cotonou`) is shown first (`coverage = official-street`); a door number, once known, replaces it.
- A compound with an official address keeps its N-Ways code, shown beside the official address, never in its place.
- When a 2026-programme town delivers its addresses, they are attached in the next sync; no N-Ways code changes.
- **Sync:**
  - re-import on each release of the holder's dataset, or monthly by API;
  - a changed official text replaces the old one, and the history is kept;
  - an official address withdrawn by the holder is removed, never invented.
- `display_address(record)` in the reference returns the official text when present, else the N-Ways form.

## 1b. The border decides

A Benin code MUST only be issued for a building whose entrance lies inside Benin's national border, the OpenStreetMap `boundary=administrative` relation of `admin_level=2` (relation 192784), or within 300 m of it (`BORDER_M`). Every other outline (the geoBoundaries arrondissements, the OCHA communes, the spot frames) is generalised and spills over the border in places; none of them decides. A point more than 300 m outside the border is in a neighbouring country, and no Benin code is issued or moved there whatever its arrondissement, code area or spot code.

- **Distance.** 0 inside the border (even-odd ray casting over every ring); else the least distance to an edge, on the local plane of the point (110,574 m per degree of latitude, 111,320 m per degree of longitude times the cosine of its latitude).
- **Build.** The pipeline uses the full boundary of the extract: footprints are kept only when their centre lies inside it, and a compound whose point lies more than 300 m outside it is dropped (`tools/README.md`, "The border decides").
- **Issue.** The server and decoders use `engine/data/border.json`, the boundary simplified so that every point of either outline lies within `toleranceM` = 50 m of the other (measured by `tools/country-border.py`: 45.0 m and 44.8 m). A point is refused when it lies more than 300 − 50 = 250 m outside the simplified outline (`bj_border.abroad`). So nothing more than 300 m outside the true border is ever accepted, and nothing inside it or within 200 m of it is ever refused.
- **Registry.** No published code has its entrance outside the full border (0 of 4,147,741).

Examples: 6.42 N, 2.76 E, about 6 km across the south-eastern border, has a spot code by section 2.4 (rule 1 reaches 10 km) but is refused; 8.32 N, 1.62 E, inside the outline of an arrondissement but 1.6 km across the western border, is refused.

## 2. Spot codes

### 2.1 Projection

- Coordinates are WGS 84. The engine projects them to **UTM zone 31N** (EPSG:32631): central meridian 3°E, scale 0.9996, false easting 500,000 m, false northing 0.
- The engine MUST use a transverse Mercator series accurate to 1 mm within Benin. The reference uses the Krüger series to n³.
- The reference matches GDAL (EPSG:4326 → EPSG:32631) to the millimetre on every test vector.

**Why UTM 31N, not latitude/longitude.**

- All of Benin is inside zone 31N.
- The ANDF cadastre is in EPSG:32631.
- Survey beacons arrive in UTM 31N.
- A metric grid gives square 3 m cells everywhere, from Cotonou (6.4°N) to Karimama (12.4°N).

### 2.2 Frame and cells

Each arrondissement has a frame:

- `e0` and `n0` are the minimum easting and northing of its outline, rounded down to a multiple of 1,000 m.
- `kx` and `ky` (3 or 4) are the number of base-20 characters per axis: 3 covers 20³ × 3 m = 24,000 m; 4 covers 480,000 m.

For a point with UTM coordinates (e, n):

```
ix = floor((e - e0) / 3)      0 <= ix < 20^kx
iy = floor((n - n0) / 3)      0 <= iy < 20^ky
```

### 2.3 Characters

- **Alphabet:** `23456789CFGHJMPQRVWX`, indexes 0–19.
- **Digits:** ix and iy are written as kx and ky base-20 digits, most significant first.
- **Interleaving:**
  1. Pad the shorter axis on the left with empty slots, so both have K = max(kx, ky) levels.
  2. For each level from the most significant, emit the northing digit (if present), then the easting digit (if present).

So the first two characters locate a 1.2 km square (a 24 km frame with 3 characters per axis), the next two a 60 m square, and the last two a 3 m cell.

- **Machine form:** `BJ-<COMMUNE>-<arr 2d>-S-<chars>`, for example `BJ-COT-09-S-35986W`.
- **Display form:** `<COMMUNE> <arr 2d> · <first 3> <rest>`, for example `COT 09 · 359 86W`.
- **Decoding** reverses the steps and returns the cell centre, (e0 + (ix + 0.5)·3, n0 + (iy + 0.5)·3), projected back to WGS 84. The decoded centre is at most 2.13 m from the encoded point.
- A point in no arrondissement outline takes its arrondissement by section 2.4; a point that section refuses MUST be rejected.

### 2.4 Points in no outline

The arrondissement of a point for the spot grid is the one whose outline holds it (section 3.1). The outlines come from a generalised boundary dataset, so some points of Benin lie in no outline: in slivers between arrondissements, along the rivers that form the northern border, and just beyond the western border. 13,999 issued compounds (0.34 %) lie there. Such a point takes its arrondissement as follows, so that every issued compound has a spot code:

1. Candidates are the arrondissements whose outline lies within 10 km of the point (`SPOT_OUTLINE_M`); the issued compounds in no outline lie at most 7.1 km from the outline they take. A point farther from every outline is outside Benin.
2. Among the candidates whose frame holds the point (0 ≤ ix < 20^kx and 0 ≤ iy < 20^ky), the one with the nearest outline: the least distance from the point to an edge of any ring of its outline, in degrees of latitude with longitude differences multiplied by cos(latitude of the point) (`bj_engine.edge_d2`). Ties go to the lower commune key, then the lower arrondissement number.
3. If no candidate's frame holds the point, the candidate with the nearest outline (same ties) among those whose frame the point lies at most 333 cells (999 m) beyond on each axis (ix and iy each between −333 and 20^k + 332); the point takes that frame's nearest cell (ix and iy clamped to 0 … 20^k − 1). 158 issued compounds on the border with Togo (Athiémé, Aplahoué, Ouaké) lie west of the frames of every arrondissement within 10 km, at most 393 m beyond one; their spot code names the frame's edge cell, and the registry keeps their exact entrance.
4. Otherwise the point MUST be rejected.

A spot code is a grid reference: a point beyond the national border may have one, but that never makes it Benin's for a code (section 1b).

Frames never move and never gain characters, because either would change spot codes already published. Decoding needs no lookup: a spot code names its arrondissement, and its cell centre is decoded in that arrondissement's frame.

Examples: a compound of Monsey, Karimama (12.2796011 N, 2.9817464 E), 1.4 km beyond the outline, lies in Monsey's frame: `KAR 05 · 349 RVMVH`. A compound of Atchannou, Athiémé (6.5089835 N, 1.6966827 E), 111 m west of every frame, takes the nearest cell of Atchannou's frame: `ATH 01 · C22 2W2`.

## 3. Code areas

### 3.1 Lookup

1. Find the arrondissement whose outline contains the point. The reference does a ray-casting point-in-polygon test with a bounding-box prefilter, in the order of `model/units/arrondissements.geojson`.
2. Within it, find the quartier or village (below).

The code areas have no published outlines; their place points are frozen. The code area of a point is the area of its arrondissement whose place point is nearest (squared distance in degrees with longitude scaled by cos² of the latitude; ties to the lower area key). An arrondissement with no named place has one area, index 000, named after the arrondissement. The code area of every issued compound is fixed in the register: a better outline later changes no code.

### 3.2 Issue rules

- The code areas, their keys, place points and numbering frames MUST be frozen before the first number in them is issued. They were frozen at first issue, on 20 October 2026.
- The quartier index is its rank in `keys.json` (OpenStreetMap place points of the arrondissement, alphabetical), frozen at first issue; the official quartiers of the Loi 2013-05 annex become aliases.
- An area whose block (section 5.1) exceeds 8,500 numbers (more than 4,250 compounds) takes five digits. It is not split: its official quartiers become aliases when the communes publish them.
- The national name table (section 5.1) MUST be built and frozen before the first number of any area is issued.

## 4. Compound registry generation

The registry is built per arrondissement, in this order:

1. **Collect** footprints (OSM, Google Open Buildings and Microsoft via the N-Ways map) whose centre lies inside the national border (section 1b), OSM barriers (`wall`, `fence`, `hedge`, `gate`…), N-Ways compounds and gates (`data/valhalla/compounds.geojsonseq`, `gates.geojsonseq`), and confirmations.
2. **Profile** every structure (section 6).
3. **Group** structures into compounds (`group_compounds`). The rules apply in this order:
   1. **Enclosure.** Closed barrier rings of 30–6,000 m². Every structure whose centroid is inside the smallest enclosing ring joins it (confidence 0.85).
   2. **Annex attach.** A structure under 30 m² that is not enclosed joins the structure of at least 30 m² with the smallest outline gap, if that gap is 6 m or less (0.6). Gap = least distance between outlines in local metres, 0 if they overlap.
   3. **Hut cluster** (the rural communes of Alibori, Atacora, Borgou and Collines; not Parakou). Huts under 40 m² that belong to no house (not an annex, not in an enclosure) and are within 3 m chain together, up to 25 per compound (0.5): a cluster never joins two houses.
   Production: `bj_engine.group_footprints` (the same rules on a 40 m grid, footprints in stable-id order).
   4. **Single** (0.4).
   5. **Confirmed groupings** override rules 1–4 (0.9). An issued code is never changed by regrouping (section 8).
4. **Entrances.**
   - Entrance 1 is the main gate, picked in this order:
     1. a confirmed gate;
     2. an OSM/N-Ways gate within 2 m of the enclosure ring;
     3. the point of the compound outline nearest the nearest road, marked "inferred".
   - In lake villages, the landing replaces the gate.
5. **Assign each compound to its code area** by its main structure's area (section 3.1); its reference point for numbering is the centre of its largest structure until a gate is confirmed.
6. **Number** each code area (section 5).
7. **Emit** the records and validate them: every structure belongs to exactly one compound, and numbers are unique per area.

## 5. Numbering

### 5.1 National name ranges

**Rule.** The remembered form `<name> · <number>` MUST identify one compound in all of Benin with no other context (no commune, no arrondissement, no device position). A code is said on the phone and written on a parcel far from where it was issued, and one area in four shares its name with another, so context cannot be relied on.

1. **Group.** Code areas are grouped by `norm_name(plate name)` (sections 7.1, 7.2). All areas of one group share one national range.
2. **Block size** of an area with C compounds at first issue: `B = max(200, ceil(2C / 100) × 100)`, at most 85,000 (90,000 − the 5,000 spare).
3. **Digits.** Let T be the sum of the group's blocks. The name has 4 digits (range 1000–9999) if T + 500 ≤ 9,000; else 5 digits (10000–99999) if T + 5,000 ≤ 90,000; else the name MUST be split by its listed qualifier (`design.json` → `nationalNames.qualifiers`; no Benin name needs one).
4. **Layout.** Blocks are laid end to end from the bottom of the range, in the order of the area key (commune key, arrondissement number, quartier index). The rest of the range, at least 500 (4 digits) or 5,000 (5 digits), is the name's spare space.
5. **Name index.** Each normalised name has a national index `i`, 1–99,999 (the rank of the name at first build; new names are appended). It is the check-digit input (section 7).
6. **Frozen.** The table is frozen at first issue. A block MUST NOT be moved, resized or renumbered, and a name's digit count MUST NOT change.
   - A new area whose name is already in the table gets `next_block`: the lowest free hundreds of the name's spare space, sized by rule 2.
   - An area whose block is full gets an extension block the same way. It keeps both.
   - A new area that does not fit the spare space takes the name's qualifier, which is a new name with its own range.
   - A new name gets the next free index and its own range.
7. **Decoding** `resolve(name, number)`: normalise, look up the plate name, else the alias table (an official name that maps to one plate name), require the number to have the name's digit count, return the area whose block contains the number. A number in the spare space MUST be rejected as not issued.

In the issued register (`model/stats/name-ranges.json`): 12,964 areas, 10,841 plate names, 1,265 names in 2+ areas covering 3,388 areas (on official names it would be 11,208, 1,024 and 2,780); 10,707 names have 4 digits and 134 have 5 (299 areas). The largest range is Ladji Farani's (one area in Parakou, 46,100 numbers in its block, 10000–56099); the largest shared range is Gouré Tépel's (two areas, 38,800 numbers).

### 5.2 Inside a block

Inside an area's block [F, F + B) with N compounds:

1. Compute each compound's Hilbert index, order 16 (65,536 × 65,536 cells over the area's frame: the box of its footprints' centres at first issue widened by 0.0005° on every side, frozen), from its reference point. The standard rotate-and-flip algorithm is in `hilbert_d`.
2. Sort the compounds by Hilbert index.
3. The main part is [F, F + floor(2B/3)). The tail reserve is the rest of the block.
4. Step s = max(1, floor(floor(2B/3) / N)). The i-th compound (from 0) gets F + i·s.
5. If 2N > B, the engine MUST refuse: the block was sized wrongly (rule 2 of 5.1 makes B at least 2N).

**New compound** (Add my home, new footprint), given existing numbers and their centroids:

1. Find its Hilbert index k.
2. Let a be the greatest main-part number whose compound has index ≤ k, and b the least with index > k.
3. Choose the free number strictly between a and b closest to (a + b)/2. Free means never issued and not retired. On a tie, take the lower.
4. If there is none, take the lowest free number in the block's tail reserve; if the block is full, an extension block (5.1 rule 6).

Numbers MUST NOT be reused. A retired code stays in the registry with status `retired`, and its number is never issued again.

**The issuer.** A new compound's number depends on every number already issued in its area, so codes MUST be issued by one issuer for the whole country, working from one register. Two issuers would compute the same free number for two homes. Other systems receive new codes through the published registry.

## 6. Structure profile

Computed per structure. Each attribute stores `{value, source, sourceId?, confirmedAt}`.

- **Footprint and perimeter.** Geodesic area and perimeter. The reference uses a local planar approximation, which is within 0.1% at this size. Production SHOULD use a geodesic formula.
- **Height.** OSM `height` only. The Google/Microsoft `h` is a rendering filler (36 values spread over 3.5–7 m) and is never used.
- **Floors.** OSM `building:levels`, else OSM `height` / 3 (rounded, at least 1), else unknown.
- **Floor area.** Footprint × floors.
- **Class.** The highest-confidence evidence wins (`design.json` → `structureProfile.inferenceConfidence`). Each other piece of evidence that agrees adds 0.05, up to 0.95. Residential plus commercial evidence gives `mixed`.
- **Name.** Only for non-residential classes, and only as published in OSM or by the business or institution itself.
- **Compound class:**
  - `institutional` if any structure is education, health, religious or government;
  - else `mixed` if dwellings and commerce;
  - else `commercial`;
  - else `industrial`;
  - else, for residential: `residential-multi-storey` if any dwelling has 3+ floors, `residential-multi-household` if 2+ dwellings of 30 m² or more, otherwise `residential-one-household`;
  - else `unclassified`.

## 7. Codes and check digit

- **Machine compound code:** `BJ-<COMMUNE>-<AA>-<QQQ>-<NNNN or NNNNN>-<C>`, the number having the digit count of the area's name.
- **Damm check:** C = Damm(iiiii ‖ NNNNN): the name's national index as 5 digits, then the number as 5 digits (zero-padded), using the standard order-10 quasigroup table in `DAMM`. Example: Zogbo (i = 10736), 4617 → Damm(`1073604617`) = 4, code `BJ-COT-09-004-4617-4`.
- **Binding.** A machine code is valid only if (a) the commune key is one of the 77 in `keys.json`, (b) the number lies in a block of that area in `names.json`, and (c) C matches. Name and number determine the area through the frozen table, so C binds name, number and area.
  - The area digits are deliberately not in the Damm input. A mistyped number can also change the area it falls in; with the area in the input, two inputs would differ and Damm would no longer guarantee detection.
  - Over name ‖ number, every single-digit error and every adjacent transposition in the number is detected, including one that lands in another block of the same name. `test_bj.py` checks this exhaustively over the real blocks of five shared names.
  - An altered area part of a machine code fails (b), because a number belongs to one block only.
- **Remembered form:** `<plate name> · <NN NN>` (4 digits) or `<plate name> · <NN NNN>` (5 digits). The plate name MUST pass `plate_ok` (section 7.2); `remembered()` refuses any other name.
  - Parsers MUST accept `Zogbo · 46 17`, `Zogbo 46 17`, `Zogbo 4617`, `Zongo · 15 200`, `Zongo 15200`, any spelling with the same `norm_name`, the official name where it is an alias (`Camp Peulh Soukoumpérou · 10 01` = `Soukoumpérou · 10 01`), and an optional `, <commune>`.
  - A code whose area's plate name is provisional (flagged for the commune) decodes like any other: codes are issued under the provisional name, which the commune may change once (the old name stays an alias).
  - `decode_remembered` MUST resolve the form alone (section 5.1 rule 7). A commune given after a comma MUST match the area's commune, or the code is rejected; it is never used to choose between areas.
  - The `·` separator is REQUIRED when the area name ends in a digit (`Ganvié 1 · 12 03`).
- **Spoken French:**
  - Four digits: two pairs, each read as a number from 0 to 99 ("quarante-huit dix-sept"). A pair starting with 0 is read "zéro" plus the digit ("douze zéro trois").
  - Five digits: a pair, then the last three digits as a hundred, as French postcodes are read: 15170 "quinze cent soixante-dix", 19300 "dix-neuf trois cents"; a group starting with 0 is read "zéro" plus the pair (10070 "dix zéro soixante-dix").
- **Sub-units:**
  - `.<n>` is a structure (1 = largest).
  - `/<n>` is an entrance (1 = main gate).
- **Link:** `https://nways.ng/a/<machine>`.

### 7.1 Name normalisation (`norm_name`)

Applied in this order:

1. Map the Gbe letters ɔ → o, ɛ → e, ɖ → d, ŋ → ng, ƒ → f, ʋ → v, ɣ → g, and œ → oe.
2. Unicode NFKD, drop combining marks, lower case.
3. Split into words on anything that is not a-z or 0-9 (spaces, hyphens, apostrophes, dots).
4. Drop a leading French article `le`, `la`, `les`, `l` when other words follow. Read the words `st` and `ste` as `saint` and `sainte` (plate abbreviations).
5. A last word that is a Roman numeral I–X or an ordinal (`1er`, `1ere`, `2e`, `2eme`, `3ieme`…) becomes its number.
6. Join the words with nothing between them.
7. Fold spellings: `tch` → `c`, `dj` → `j`, `ph` → `f`, `ou` before a, e, i or y → `w`, and any doubled letter → one.

Examples (all in `test_vectors.json` → `normalised`): Gbèdji, Gbedji, Gbédji → `gbeji`; Ganvié I, Ganvié 1, Ganvie 1er → `ganvie1`; Ouèssè, Wèssè → `wese`; Tchetti, Ceti → `ceti`; Ouémè Hounli, Ouèmèhounli → `wemehounli`; La Haie Vive, Haie-Vive → `haievive`.

### 7.2 Plate names

The name in a remembered code is short, because it is said on the phone and painted on a gate. Every code area has an **official name** (keys.json `name`, printed in small type, never required) and a **plate name** (keys.json `plate`, or `name` when they are equal).

- **Limit** (`plate_ok`, using `plate_names.fits`): at most 12 characters, counting every character of the NFC form once (an accented letter, a space, a hyphen, an apostrophe each count 1), and at most 2 words. Words are the parts between spaces or hyphens; the linking words `de du des d' la le les l' et sur en au aux à es` do not count. Digits are allowed in Benin (`DIGITS_OK`): an ordinal that is part of the name stays.
- **Derivation** (`tools/bj_plates.py` over `engine/reference/plate_names.py`; only at table build, never at decode):
  1. documented short form with source (`KNOWN`, empty so far);
  2. clean: close a one-sided spaced hyphen (`Lèlè- Honmèho` → `Lèlè-Honmèho`), drop quotation marks, brackets, text after `/`, the mapping placeholder `nom_loc`, a leading `Camp`/`Campement` before `Peulh`, the French generic words (`Quartier Cité Lotissement Zone Secteur Village Hameau Campement`, `Village de`, `Site des logements sociaux`) and a genitive left at an end (`Cité de X` → `X`); a removal that leaves only weak words or starts or ends on another linking word is not made; all-capital names are recapitalised;
  3. if it fits: done (`as-is` or `cleaned`);
  4. `Saint`/`Sainte` → `St`/`Ste` if that fits (`abbreviated`);
  5. candidates: runs of whole words that fit, never starting or ending on a linking word, never only weak words, never splitting a binding word from the next (`Saint`, `Aladji`, `El Hadj`, `Orou`, `Bio`, `Sabi`…); scored by national rarity of their words, × 1.5 for the run that ends the name, × 0.1 if it drops a qualifier (a weak word after the name: `Peulh Bariba Gando Dendi Haoussa Gah Gouré Gnel Kparou Centre Gare Plage Nord Sud Est Ouest`, an ordinal…);
  6. the best is taken (`distinctive`) only if it has no note, scores at least 1.5 × the next, has 4 letters or more, and is not in the avoid set (77 commune seats + Calavi, Dassa, Missérété, Sèmè, Bossito; 12 department names; the big towns and the names of the four neighbouring countries; minus the area's own commune);
  7. else `council`: `needsCouncilChoice`, up to 3 `plateCandidates` (4 letters or more, not a generic word; no plate name or candidate begins or ends with a hyphen, apostrophe or other punctuation), the first used provisionally; a hyphenated name with no candidate offers its parts. With no candidate, the cleaned name is kept and fails `plate_ok`.
- **Numbering** uses the plate name (section 5.1). **Aliases:** each normalised official name that differs from its plate name maps to it, unless it would map to two plate names or is itself a plate name (then it is in `aliasesDropped` and does not decode).
- **Issue rule:** every area is issued, a flagged one under its first candidate, or its cleaned name when it has none, so that no home waits for a naming decision; the commune may choose once, and its choice is added as an alias. People never see or type a check digit; it lives in the machine form only.

## 8. Stability rules

| Event | Effect |
|---|---|
| New building inside an existing compound | New structure index. Compound code unchanged |
| New compound | Number by section 5.2 (provisional until confirmed) |
| New area with an existing name | `next_block` from the name's spare space (5.1). Existing blocks unchanged |
| Area block full | Extension block from the name's spare space (5.1) |
| Demolished compound | Code retired, never reissued |
| Split | Part with entrance 1 keeps the code. The other gets a new number |
| Merge | Oldest code survives. The others become aliases in `registry/aliases.json` |
| Plate name chosen or changed by the commune | Alias only: the old plate name keeps decoding; blocks unchanged |
| Quartier renamed, arrondissement redrawn | Alias table only. Machine codes and blocks unchanged; the area keeps its block in its original name's range |
| Engine change | MUST NOT change any issued code. `test_vectors.json` diffs are reviewed |

## 9. Offline behaviour

- **Spot code and code area.** Computed on the device from `keys.json` and the outlines. No network needed.
- **Compound code.** Looked up in the cached registry slice.
- **Remembered code → area.** Decoded on the device from `names.json` alone, anywhere in Benin.
- **Add my home while offline.**
  - The spot code is shown at once.
  - The provisional compound number is requested on the next connection, because two offline phones must not take the same reserved number.
  - The app queues the outline and gate.

## 10. Add my home: checks

The issuer applies these checks to every new code (the server in `server/` applies the same):

- **In Benin.** The point lies at most 300 m outside the national border (section 1b), and in an arrondissement outline, or, in none, section 2.4 gives it an arrondissement (a spot code); a point that section refuses is outside Benin. The lookup of the code at a point uses the same test, so a compound in a gap between outlines is found by point and can have another door.
- **Already coded.** A request within 3 m of an issued entrance, inside an issued compound's structure, or with an outline sharing more than half of the smaller of the two outlines with one, is answered with the code the building already has.
- **Outline.** The ring is closed and covers 6 m² to 2 ha.
- **Area.** Another door of a compound takes that compound's area and must be within 80 m of its entrance. A new compound takes the area of the nearest issued code within 250 m, so that a new house joins its neighbours; failing that, the code area of the point (section 3.1); failing that (a point in no outline), the nearest area.
- **Number.** Section 5.2; a full area takes an extension block (section 5.1 rule 6).

The app adds its own checks before it sends a request:

- **Gate.** It lies within 3 m of the outline.
- **AR walk.** The AR shape and the GPS track agree within 5 m RMS after best-fit translation; the fitted shape is placed with the GPS mean.
- **Survey plan.** Beacons are UTM 31N (EPSG:32631) metres, close, and fall inside the arrondissement frame.
- **Land.** An outline overlapping a given ANDF parcel by more than 10 % of the smaller area is flagged: a code is an address, not a title.

## 11. Conformance

An implementation conforms if it reproduces every value in `reference/test_vectors.json`:

- `damm`;
- `spot` (machine, display, area, decoded centre to 1e-7°);
- in `reference/vectors.json`, `spotsOutside`: points in no outline (issued compounds of Athiémé, Karimama and Ouaké, slivers, the frames' nearest cells and refusals) with their arrondissement, machine and display forms and decoded centre (section 2.4);
- `machine`;
- `remembered`;
- `spokenFr`;
- `normalised` (name → key);
- `sameName`: remembered forms of same-named areas (Zongo in Cotonou and Djougou, Agata in Cotonou and Dangbo, Gbèdji in Porto-Novo and Allada) decoding to their different areas and machine codes;
- `notIssued`: numbers in a name's spare space, or with the wrong digit count, rejected;
- `plateLength` (characters, words, `plate_ok`) and `plateNames` (official name → plate name, rule, flag);
- `officialAlias`: an official name typed in full decodes to the same machine code as its plate name;
- `collideAfterShortening`: two areas whose names differ but whose plate names are the same (Flessa in Zagnanado and Zogbodomey; Gbégoudo in Akpro-Missérété and Zè) decode to their different areas;
- `plateRefused`: remembered codes of flagged areas whose provisional plate name is over the limit: they decode, because those areas are issued under that name, while `remembered()` refuses such a name unless it is marked provisional;
- `compoundSample`: structures, compounds, numbers and the provisional number for the real Cotonou block in `reference/testdata/`.
