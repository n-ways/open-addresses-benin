# The N-Ways address model for Benin: design notes

These notes explain the choices behind the model: what was compared, what was measured and why each rule is what it is. The normative description is [engine/SPEC.md](../engine/SPEC.md); the research paper ([paper.md](paper.md), [paper.fr.md](paper.fr.md)) sets the model in its context. The machine-readable summary of every decision is [model/design.json](../model/design.json).

The register was issued on 20 October 2026: 4,147,741 codes, one for every compound in Benin, Cotonou included. Figures marked "issued" come from that register (`model/stats/building-stats.json`, `model/stats/name-ranges.json`); figures marked "design" are the estimates the choices were made on, before the compounds were grouped.

## 0. Official addresses first

Where the State gives an address, that address is the one people should see. Two rules follow.

1. **The official address is shown first, exactly as written.** In Cotonou the 2013 addressing plan gives every street a code (`Rue 12.217`: arrondissement 12, street 217) and every door a metric number (`N° 43`). The plan's door numbers are held by the Commune and are not open data; the street codes are on the ground and in OpenStreetMap (307 coded streets). So every Cotonou compound within 30 m of a coded street shows that street first (`Rue 12.202, Cotonou`: 17,948 issued compounds), and a door number of the plan replaces the street as soon as it is known for the gate. The national programme approved on 22 April 2026 will give addresses in the Grand-Nokoué towns first; they will be attached the same way when they are delivered.
2. **Every compound also has its N-Ways code**, beside the official address, never in its place. An official address can be incomplete (a street without a door number), can change, and does not exist in most of the country; a code that every compound has, from the first day and in the same form everywhere, is what lets a courier, an ambulance or a census team reach any home. The N-Ways code never competes with an official number on a gate: where a door number of the plan exists, the plate shows that number.

| Area | Official system | What is shown |
|---|---|---|
| Cotonou, door numbered by the 2013 plan | `N° 43, Rue 12.217` (Commune of Cotonou) | the official address; the N-Ways code beside it |
| Cotonou, coded street, no door number known | `Rue 12.202, Cotonou` | the official street; the N-Ways code beside it |
| Towns of the 2026 national programme | none delivered yet | the N-Ways code; the official address first once delivered |
| The rest of Benin (villages, quartiers, lake villages) | none | the N-Ways code |
| Everywhere | La Poste boxes (`10 BP 648 Cotonou`) | not an address; kept as free text |

Benin has no postcode (`docs/existing-systems.md`). An N-Ways code is never called a postcode or an official address.

## 1. First criterion: easy to remember, easy to get

An address works only if the people who live there can say it from memory to a courier, a nurse or a taxi driver. Cotonou's street codes are precise but rarely said; most people still give a quartier and a landmark ("Zogbo, derrière la pharmacie"). Every choice below was tested against one question: can a resident of Zogbo, Ganvié or Parakou remember the code after hearing it once?

### 1.1 What people already remember

| Habit | Evidence | Consequence |
|---|---|---|
| The quartier or village name | Law 2013-05 divides Benin into 5,290 villages and quartiers de ville; directions start with the quartier | The code starts with that name, in a short form of at most 12 characters and 2 words (section 2.3) |
| Numbers in pairs | Telephone numbers are read in pairs in French ("01 97 12 34 56") | The number has four digits, read as two pairs: "46 17", "quarante-six dix-sept". Names shared by many large areas take five digits, read like a French postcode: "15 200", "quinze deux cents" (section 2.2) |
| The arrondissement number in Cotonou | Street codes begin with it ("Rue **12**.217") | The machine code carries the arrondissement number |
| Landmarks | "près de", "derrière", "en face de" | The landmark line stays beside the code, never instead of it |

### 1.2 The options compared

The design counts came from the N-Ways building map (OpenStreetMap, Google Open Buildings and Microsoft footprints): 5,174,482 structures, of which 1,040,021 from OpenStreetMap. Compounds were estimated at 0.813 per structure (the Cotonou grouping of section 3), about 4.2 million; the issued register has 4,147,741. The capacity rule is that the numbers available are at least twice today's compounds, leaving room for growth and infill.

| Option | Example | What people must remember | Arithmetic | Verdict |
|---|---|---|---|---|
| A. National digits only | 4617305 | 7 digits, no place | 4.2 M × 2 = 8.4 M → 7 digits | Too long, and says nothing about where |
| B. Commune + digits | Cotonou 108 417 | name + 6 digits | Abomey-Calavi: about 384,000 compounds × 2 → 6 digits | Too long |
| C. Arrondissement + digits | Godomey 137 081 | name + 4 to 6 digits | 546 arrondissements, median 7,052 structures; 206 fit 4 digits, 336 need 5, 4 need 6 | Lengths vary; outside the cities the arrondissement is not the name people say |
| D. Arrondissement + 4–5 base-20 characters | Godomey 7HQ2X | name + letters and digits | 20⁴ = 160,000 fits all but Godomey | Letters are hard to say and hear in French ("cé", "pé", "vé" rhyme); in Fon "c" reads "tch", "x" is a velar fricative and there is no "q". Kept only for spot codes, which travel as links |
| **E. Quartier or village + 4 digits** | **Zogbo · 46 17** | **a name they already use + 4 digits** | Cotonou areas: median 1,067 compounds, largest 4,124 (design). Nationally 84.4 % of compounds are in areas that fit 4 digits (design); issued: 3,241,198 codes have 4 digits and 906,543 have 5 | **Chosen** |

**One length, not three digits for small villages.** About 10,861 named-place areas could have used three digits (450 compounds or fewer). A single length is easier to teach ("toujours deux paires"), fits one plate design and never changes when a village grows past 450 compounds, which three digits would force.

**Five digits for some names.** The code must be unique in all of Benin on its own (section 2.2). A name carried by many areas, or by a few large ones, needs more than 9,000 numbers between them. In the issued register 134 of the 10,841 plate names have five digits, covering 299 of the 12,964 areas. The length belongs to the name, was fixed at first issue and never changes.

**The check digit is not remembered.** The Damm check digit (section 7) is in the machine form only. People never see it, say it or type it: plates and written forms show the name and the number.

### 1.3 Getting the code with no effort

| Situation | What the resident does | What happens |
|---|---|---|
| Has the N-Ways app and saved "Maison" | nothing | the home card shows "Votre adresse : Zogbo · 46 17", or the official address first where one exists |
| Standing at the gate | opens the app | "Vous êtes devant Zogbo · 46 17" |
| Wants to send it | one tap, "Partager" | a WhatsApp or SMS message with the code, the landmark line and the link `nways.ng/a/BJ-COT-09-004-4617-4` |
| No smartphone | nothing | the code is on the gate plate or sticker (section 9); anyone with the app can look it up |
| Courier, partner or public service | one API call | point → code and code → gate, through the N-Ways API or a deployment of `server/` |
| New house | "Ajouter ma maison", four short steps (section 8) | a provisional code at once |

## 2. The code, in three forms

| Form | Example | Used by |
|---|---|---|
| Remembered (said) | **Zogbo · 46 17** ("Zogbo, quarante-six dix-sept") | residents, callers, drivers |
| Written | Zogbo · 46 17 (commune and arrondissement in small type on a plate, as a help to the eye) | plates, forms, messages |
| Machine | **BJ-COT-09-004-4617-4** | apps, APIs, the registry, QR codes |

The machine form has these parts: `BJ` the country; `COT` the commune key (section 2.1); `09` the arrondissement number; `004` the quartier or village index in the arrondissement; `4617` the number, inside the block of Zogbo's national range given to this area; `4` the Damm check digit over Zogbo's national name index and the number (`10736` ‖ `04617`, section 7).

The remembered and machine forms map one to one through the national name table (`model/names.json`). The remembered form needs no commune, no arrondissement and no phone position.

Sub-units, used only when needed: `Zogbo · 46 17 .2` is structure 2 of the compound (an annex, a boutique); `Zogbo · 46 17 /2` is entrance 2 (entrance 1 is the main gate). Flats in an immeuble are not coded; the resident adds "appartement 3B" as free text.

### 2.1 Commune keys and arrondissement numbers

- **Commune keys:** 77 three-letter keys that read as the name: COT Cotonou, CAL Abomey-Calavi, PNO Porto-Novo, PKO Parakou, SOA Sô-Ava, SEM Sèmè-Podji, OUI Ouidah, NAT Natitingou, SVL Savalou, SAV Savè… (`tools/build_keys.py`, `model/keys.json`).
- **Arrondissement numbers:** the official ordinal where the name carries one (Cotonou 1–13, Porto-Novo 1–5, Parakou 1–3, Natitingou 1–4, Djougou 1–3, Bohicon 1–2…), elsewhere alphabetical order after the ordinals. In Cotonou the number is the one on the street plates.
- **Quartier and village index:** the alphabetical rank of the named OpenStreetMap place in its arrondissement (12,932 places in 514 arrondissements; the 32 arrondissements with no named place have one area, index 000, named after the arrondissement). The index is frozen. The official list of the annex of Law 2013-05 maps onto the areas through the alias table when it is published in machine-readable form; it never renumbers them.

All keys were frozen at first issue.

### 2.2 One name, one national range

A remembered code is said on the phone, written on a parcel and typed by a courier in another town. It must name one compound in Benin on its own. Adding the commune when a name repeats, or letting the app ask "which one?", was considered and rejected: one area in four shares its name with another, so the question would be asked every day, and a code written down without its commune would be ambiguous for ever.

**How often names repeat** (issued register, `model/stats/name-ranges.json`):

| | Plate names | Official names |
|---|---|---|
| Distinct names after normalisation | 10,841 | 11,208 |
| Names carried by two or more areas | **1,265** | 1,024 |
| Areas carrying a repeated name | **3,388** (26.1 %) | 2,780 (21.4 %) |
| Most repeated | Zongo (26 areas: Cotonou, Djougou, Bassila, Malanville, Sèmè-Podji…), Kpodji (20), Kpota (19), Gbèdji (15) | |

Shortening (section 2.3) adds 337 names that are shared only because two long names end the same way ("Vakon Gbégoudo" and "Gbégoudo" are both Gbégoudo). They are numbered like any other shared name.

**The rule.**

1. **Normalised name.** Two plate names are the same when they fold to the same key (`norm_name`, SPEC 7.1): case and accents folded; the Gbe letters ɔ ɛ ɖ ŋ read o e d ng; hyphens, spaces and apostrophes removed; a leading French article dropped; a trailing ordinal written as a digit (Ganvié I = Ganvié 1 = Ganvié 1er); and the spellings of one sound folded: tch → c (Fon c is "tch"), dj → j, ou before a vowel → w (Ouidah/Widah, Houéyiho/Hwéyiho), ph → f, doubled letters → one (Dassa/Dasa). St and Ste read as Saint and Sainte.
2. **One national range per name:** 1000–9999 for a four-digit name, 10000–99999 for a five-digit one.
3. **Blocks.** The range is cut into one block per area, laid out from the bottom in the order of the area keys. A block is twice the area's compounds at first issue, on whole hundreds, at least 200: max(200, ⌈2C/100⌉ × 100).
4. **Spare room.** The top of every range stays free for future areas of the name: at least 500 numbers for a four-digit name, 5,000 for a five-digit one. A name takes four digits when its blocks plus 500 fit in 9,000, otherwise five when its blocks plus 5,000 fit in 90,000.
5. **Decoding.** Name and number → normalised name → its range → the one block holding the number → one area and one compound. The official name typed in full finds the same range when it belongs to one plate name only (an alias). A number in the spare space is "not issued". A commune given after a comma is checked, never needed.
6. **Qualifier.** A name whose blocks would not fit five digits would be split once by a qualifier people already say. No Benin name needs one: the largest range, Ladji Farani's in Parakou (one area, 23,009 compounds), uses 46,100 of its 90,000 numbers; the largest shared one, Gouré Tépel's (two areas), 38,800.
7. **Large areas are not split.** An area whose block exceeds 8,500 numbers (more than 4,250 compounds) takes five digits and keeps one block: 118 areas, most of them whole towns that OpenStreetMap names with one point (Ladji Farani, Lokossa, Cococodji, Tanguiéta, Malanville…). When the communes publish their official quartiers, the quartier names become aliases and the codes stay as they are.

**Examples (issued codes).**

| Remembered | Area | Machine |
|---|---|---|
| Zongo · 15 200 | Zongo, 5e arrondissement, **Cotonou** | `BJ-COT-05-005-15200-4` |
| Zongo · 19 500 | Zongo, 1er arrondissement, **Djougou** (380 km north) | `BJ-DJO-01-040-19500-0` |
| Agata · 10 00 / 15 00 / 26 00 | Agata in **Allada**, **Cotonou** and **Dangbo**: one name, three blocks | `BJ-ALL-06-001-1000-4`, `BJ-COT-06-001-1500-8`, `BJ-DAN-01-001-2600-0` |
| Gbèdji · 13 400 (or Gbédji, GBEDJI) | Gbèdji, 1er arrondissement, **Porto-Novo** | `BJ-PNO-01-001-13400-2` |
| Zogbo · 46 17 | Zogbo, 9e arrondissement, Cotonou (the only Zogbo: four digits, block 1000–8299) | `BJ-COT-09-004-4617-4` |

**Frozen at issue.** The block table is part of the issued data. A block is never moved, shrunk or renumbered, even if its area's name changes later (a rename adds an alias). A new area with an existing name takes the next block from the name's spare space (`next_block`), and so does an area that has filled its own block (an extension block, also frozen). A name's digit count never changes.

### 2.3 Plate names: a short name in the code

The name in a remembered code is said on the phone and painted on a gate, and map names are not always short: "Camp Peulh Soukoumpérou", "Poste forestier des Chutes de Koudou", "Flessa (quartier des forgerons)". So every code area has two names:

- the **official name**, the full name of the area as in the map (and, once published, the annex of Law 2013-05), printed in small type and never required;
- the **plate name**, the name in the code: **at most 12 characters and 2 words.** Every character counts one (an accented letter, a space, a hyphen, an apostrophe). A word is a part between spaces or hyphens ("Haie-Vive" is two words); linking words (de, du, des, la, le, les, l', d', et, sur, and the Arabic "es" of "Dar Es Salam") do not count. An ordinal that is part of the name stays ("Ganvié 1"); the "·" keeps it apart from the number.

Twelve characters and two words hold 11,134 of the 12,964 area names unchanged (85.9 %), and the longest written code whose name is within the limit, "Djèvié-Wadon · 10 000", has 21 characters (median 16; `model/stats/evaluation.json`).

**How the plate name is chosen** (`tools/bj_plates.py`, the rule in `engine/reference/plate_names.py`), in this order:

1. **A documented short form** people already say, with its published source. None is recorded yet.
2. **Cleaning.** Text in brackets or after a slash goes ("Flessa (quartier des forgerons)" → Flessa), and so do the French generic words Quartier, Cité, Lotissement, Zone, Secteur, Village, Hameau, Campement ("Mèko Village" → Mèko). "Camp Peulh X" is said "Peulh X", the Fulani camp of X. A name in capitals gets ordinary capitals. A one-sided spaced hyphen ("Lèlè- Honmèho") is closed up and quotation marks go. A doubled word is the name itself and stays ("Wari Wari").
3. If the cleaned name fits, it is the plate name: 11,134 areas as they are and 70 after cleaning.
4. **Saint, Sainte** become St, Ste when that makes the name fit ("Saint Prosper" → St Prosper). The name key reads them back, so the full form still decodes.
5. **Otherwise the most distinctive whole words**: the run of at most 2 words and 12 characters whose words are rarest among Benin's area names, with a preference for the end of the name ("Camp Peulh Soukoumpérou" → Soukoumpérou, "Lokokpo Carrémè" → Carrémè). It is taken automatically only when it is clearly ahead of the next choice and is not the name of a town elsewhere: 460 areas.
6. **Otherwise the commune chooses** (`needsCouncilChoice`) among up to 3 candidates: 1,300 areas. A qualifier would be dropped ("Akassato Centre", "Moudouro Peulh", "Nazounmè Gare"; Peulh, Bariba, Gando, Dendi, Haoussa, Gah, Gouré, Gnel and Kparou name the people or the kind of settlement, so "Nanankpo Bariba" and "Nanankpo Peulh" are two places); a hyphenated name joins two names ("Akpakpa-Dodomè"); two choices are as good; or the best choice is another town.
7. **A word is never cut**, and neither is a person's name inside a place name (Aladji, El Hadj, Orou, Bio, Sabi stay with the name that follows).

**Flagged areas are issued.** Every one of the 1,300 flagged areas has its codes, under its first candidate, or under its cleaned name when it has none: no home waits for a naming decision. 681 of them keep a name over the limit, mostly single Fon or Gun words of more than 12 letters ("Tchanhounkpamè", "Hounkponouhoué") that cannot be shortened without cutting a word. The commune may choose a plate name once; the new name is added as an alias and the numbers never change.

**The avoid list.** A plate name chosen automatically never equals another town: the 77 commune seats (which include the 12 department capitals) with the short forms people use for some of them (Calavi, Dassa, Missérété, Sèmè, Bossito), the 12 department names, and the big towns and names of the four neighbouring countries. A quartier inside its own commune may carry the commune's name.

**Official names still decode.** The official name of an area is an alias of its plate name in `model/names.json` (1,109 aliases): "Camp Peulh Soukoumpérou · 10 01" and "Soukoumpérou · 10 01" are the same compound. An official name that would point to two plate names, or is itself another area's plate name, is not an alias (`aliasesDropped`, 5 names).

| | Official names | Plate names |
|---|---|---|
| Names over 12 characters | 1,794 | 681 (all flagged) |
| Names over 2 words | 191 | 0 |
| Longest remembered code (names within the limit) | "FORET SACREE ''HOUIANHOUEZOUN'' (TINOU/KOUDO) · 10 00", 53 characters | "Djèvié-Wadon · 10 000", 21 characters |

The design estimate, made on a 1-in-10 building sample, gave 47 five-digit plate names (222 areas). The issued blocks are sized on the compounds actually grouped, and 134 names (299 areas) took five digits.

## 3. The addressable unit: the compound (concession)

People in Benin live in compounds, not in footprints. A walled concession holds the main house, a kitchen, a guardian's room, sometimes boutiques built into the street wall, and one gate. The address belongs to the compound, its structures are sub-units, and **the gate is where a driver must stop**, not the centre of the largest roof.

### 3.1 Compound types

| Type | Where | How the model treats it |
|---|---|---|
| Concession familiale, cour (several buildings, one gate, often several households) | everywhere; dominant in Cotonou, Porto-Novo, Abomey | one compound |
| Villa in a walled plot (annexes: guardian, kitchen, garage) | Haie Vive, Fidjrossè, Cocotomey, Calavi | one compound, annexes as structures |
| Maison en bande, "entrer-coucher" (rental rooms off a yard) | Cotonou, Calavi, Parakou | one compound; rooms not coded |
| Immeuble R+n | Ganhi, Jéricho, Haie Vive | one compound; flats not coded; street-level shops get their own entrances |
| Boutiques built into the front wall | every commercial street | extra entrances (`/2`, `/3`); a boutique held separately gets its own code |
| Cité, lotissement with one main gate | Calavi, Cotonou | the estate is a container with its own gate; each compound inside keeps its number |
| Tata somba, takienta (fortified earth house) | Atacora | one structure, one compound, its single door the entrance |
| Rural concession without a wall | Borgou, Alibori, Atacora, Collines | hut-cluster rule (section 3.2) |
| Maison sur pilotis (stilt house) | Sô-Ava lake villages: Ganvié, Vekky, Houédo-Aguékon… | one compound per platform; entrance 1 is the landing (ponton), reached by pirogue |

### 3.2 Grouping footprints into compounds

The registry groups structures into compounds before numbering (`group_compounds`, `group_footprints`), in this order:

1. **Mapped enclosure.** A closed OpenStreetMap wall, fence or hedge of 30–6,000 m² makes one compound of every structure whose centre is inside (confidence 0.85). A larger enclosure with many compounds is an estate.
2. **Annex attach.** A structure under 30 m² joins the nearest structure of 30 m² or more within 6 m (0.6): kitchens, latrines, guardian's rooms, kiosks against the wall.
3. **Hut cluster** (the rural communes of Alibori, Atacora, Borgou and Collines; not Parakou). Huts under 40 m² that belong to no house and lie within 3 m of each other chain into one compound, up to 25 structures (0.5).
4. **Otherwise** the structure is its own compound (0.4).
5. **People confirm.** "Ces bâtiments sont une seule maison" and "voici le portail" are recorded in the app; agreement from residents, couriers and repeat arrivals settles a grouping, as it settles map corrections.

Issued: 4,147,741 compounds from 5,174,482 structures (1.25 per compound): 3,329,544 single, 739,537 with annexes, 76,949 hut clusters, 1,711 mapped enclosures. In Cotonou: 104,101 compounds from 127,468 structures.

**Regrouping never changes an issued code.** If two compounds turn out to be one, the older code survives and the other becomes an alias; if one turns out to be two, the part with the gate keeps the code and the other part gets the next free number.

Walls and gates are rarely mapped (in Cotonou 464 closed enclosures and 94 gates, mostly schools, churches and large villas), so most real compound boundaries will come from people and imagery. The grouping is a floor, not a measurement.

## 4. Building profile

Every structure carries a profile and every compound a summary: use, size and floors, each with its source.

### 4.1 Use classes

| Class | Benin forms | Main evidence |
|---|---|---|
| residential | concession familiale, villa, maison en bande, immeuble d'habitation, case, tata somba, maison sur pilotis | OSM `building=house/residential/apartments/hut/stilt_house`; default |
| commercial | boutique, kiosque, magasin, marché (Dantokpa, Ouando), station-service, banque, maquis | N-Ways places inside the footprint; OSM shop, amenity |
| office, government | bureau; mairie, préfecture, commissariat, camp militaire | OSM office, government, townhall, police |
| education, health, religious | école, CEG, lycée, université; CHU, centre de santé, pharmacie; église, mosquée, temple vodoun | places and OSM tags |
| industrial, hospitality, transport, agricultural | entrepôt, hangar, usine; hôtel; gare routière, garage, port; ferme, grenier | OSM tags; a footprint of 2,500 m² or more as a weak prior for industrial |
| mixed | shop on the ground floor with housing | residential and commercial evidence on one structure |
| annex | cuisine, latrines, guérite | under 6 m², or an attached annex |
| under_construction, ruin, unknown | chantier, ruine | OSM `construction`, `ruins`; no evidence |

### 4.2 How sure a class is

The highest-confidence evidence wins and each agreeing source adds 0.05: an OSM building tag 0.85, an OSM point of interest on the footprint 0.75, an N-Ways place inside it 0.65, OSM land use around it 0.5, the residential default 0.45 to 0.55, size alone 0.3 to 0.4. A person confirming at the door gives 0.9; a partner's list (schools, health facilities) 0.8.

Most classes rest on the default rule: of the 5,174,482 issued structures, 5,152,555 are residential, most by default. The class mix will move as door confirmations and partner lists arrive; the model is built to correct it, not to pretend it is right.

### 4.3 Size and floors

Footprint and perimeter are computed on the outline (Cotonou median footprint 69 m²; country 45 m²). Floors come from OpenStreetMap only: `building:levels` where tagged (3,891 structures), else `height` / 3 (77), else one floor. The heights of the Google and Microsoft footprints are not used: they take 36 distinct values spread between 3.5 and 7 m and carry no floor information. Floor area is footprint × floors.

### 4.4 Source and date on every attribute

Each attribute stores its value, its source (`osm` with the element id, `google-open-buildings`, `microsoft-buildings`, `nways-places`, `door-confirmation` with a count of people and never who, `partner` with the dataset, `add-my-home`) and a confirmation date. A stronger source replaces a weaker one; the old value stays in the history.

## 5. Spot codes: any point

Not every place is a compound: a market stall, a field, a fishing spot on Lake Nokoué, a building site. A spot code works everywhere, offline, from coordinates alone.

- **Grid: 3 m cells on UTM zone 31N** (WGS 84, EPSG:32631). All of Benin (0.77° to 3.85° E) lies in zone 31N, the ANDF cadastre uses EPSG:32631, and survey plans give beacon coordinates in it, so a plot from a plan imports with no reprojection. A 3 m cell is smaller than the gap between two doors in a dense street.
- **Frame:** per arrondissement, from the south-west corner of its outline rounded down to 1 km; 3 base-20 characters per axis cover 24 km, 4 cover 480 km. Easting and northing characters alternate, so nearby points share their first characters. 406 arrondissements need 6 characters, 58 need 7 and 82 need 8.
- **Example:** the entrance of Zogbo · 46 17 is `COT 09 · 25R FH7` (machine form `BJ-COT-09-S-25RFH7`).
- **Points in no outline:** the arrondissement outlines are generalised, so 13,999 issued compounds (0.34 %, mostly along the northern borders of Ségbana, Malanville and Karimama) lie in no outline. Such a point takes, among the arrondissements whose outline lies within 10 km, the one with the nearest outline whose frame holds it (ties to the lower commune key, then number); if no such frame holds it, the nearest cell of a frame at most 999 m away. 158 compounds on the border with Togo lie west of the frames of every arrondissement within 10 km and take the edge cell of the nearest, at most 392 m from their entrance. Every issued compound therefore has a spot code. Frames never move, because moving one would change spot codes already published; a point farther from Benin is refused.
- **Alphabet:** `23456789CFGHJMPQRVWX`, no vowels (so no words) and no 0/O or 1/I/L. Spot codes are shared as links and QR codes, not memorised, so letters are acceptable here and nowhere else.

## 6. Entrances and doors

Every compound has at least one entrance; entrance 1 is the main gate. Kinds: `gate` (portail), `door`, `shop-door`, `estate-gate`, `landing` (a ponton in the lake villages), `service`. An entrance stores its position, the bearing to the street, a gate photo if the household chose to add one, the Cotonou street code and door number where they exist, and the date it was confirmed. Navigation ends at entrance 1, or at the estate gate when the estate's roads are private.

## 7. Check digit

**Damm's algorithm** over the name's national index (five digits, from `model/names.json`) followed by the number (five digits, zero-padded): for Zogbo · 46 17, Damm(`10736` ‖ `04617`) = 4.

- **It binds name, number and area.** Name and number fix the area through the frozen block table, so a matching check digit fixes the area too. The machine form also carries the area (`COT-09-004`), and a validator rejects it unless the table puts that number of that name in exactly that area.
- **The area digits are not in the sum.** A wrong digit in the number can also move it into another block, and so another area. With the area digits in the sum, two inputs would change at once and Damm would lose its guarantee. Over name ‖ number it keeps it: every single wrong digit and every swap of two neighbouring digits in the number is caught, including one that lands in another area of the same name. The tests check this exhaustively over the real blocks of five shared names.
- **It is numeric** and only in the machine form. People never see it or need it.
- A wrong **name** changes the name index, which the check catches nine times in ten; the name itself is checked against the name table.

## 8. New homes: "Ajouter ma maison"

For houses not yet on the map.

1. **At the gate.** The phone averages its position for a few seconds; this becomes entrance 1.
2. **Outline the plot,** by tapping the corners on imagery, by walking the boundary inside the wall (the shape from the camera's world tracking, placed by the averaged position and checked against imagery and neighbouring footprints), or by importing the beacons of the plan parcellaire, which are in UTM 31N.
3. **Describe it:** households, structures, floors, use.
4. **Provisional code at once**, by the rule of SPEC 5.2: a free number between its neighbours on the area's Hilbert curve, else the area's tail reserve, else an extension block of its name.
5. **Confirmed** when deliveries or visits arrive at the gate and no neighbour disputes the outline, or when new imagery and footprints agree.

**Safeguards.** An N-Ways code is an address, not a land title: only a titre foncier or a plan drawn by a licensed surveyor (ingénieur géomètre agréé) has legal value (Code foncier et domanial). A request at a building that already has its code returns that code. Outlines must cover 6 m² to 2 ha. Only the outline is kept, never photos of people or interiors. Offline, the spot code is shown at once and the compound code comes on the next connection, because two phones offline must not take the same number.

Codes are issued by one issuer only, so that no number is ever given twice (`server/README.md`, "One issuer").

## 9. Plates and stickers

- Large: **ZOGBO · 46 17**, the plate name and the number.
- Small: the official area name where it differs (*Camp Peulh Soukoumpérou*), the commune and arrondissement (*Cotonou · 9e arr.*), and a QR code to `nways.ng/a/<machine>`. The check digit is not printed: it is inside the QR link.
- Where an official door number of the 2013 plan exists, the gate keeps that number and N-Ways adds only a QR sticker on request, linking to the gate position, never a competing number.

## 10. Stability

- **Numbers.** Inside each area's block, compounds are numbered along a Hilbert curve with a step that leaves gaps for infill. The top third of the first block is a tail reserve (for Zogbo, block 1000–8299: main part 1000–5865, tail 5866–8299). Numbers are never reused.
- **Buildings.** Demolished: the code is retired and stays listed. Split: the part with the gate keeps the code. Merged: the older code survives and the other becomes an alias.
- **Map.** Areas, keys and blocks are frozen. A renamed quartier or redrawn arrondissement changes only the alias table.

## 11. Privacy

- **Codes describe places, never people.** No resident's name, phone number or identity number (NPI) is stored with a residential compound. Businesses and public buildings may show the name they publish.
- **Public:** the code, the entrance position, the profile (use, size, floors).
- **Private:** who confirmed what; gate photos (shown to the household and to a courier on an active delivery only); households and their descriptions; new outlines until confirmed.
- **Private door.** A household can ask for its entrance to be hidden from the public map; the code stays and leads a visitor who has it.
- **Law.** The processing falls under Law 2017-20 (Code du numérique), supervised by the APDP: prior declaration, and authorisation for any transfer abroad or link to an identifier (articles 391, 405, 407).

## 12. Governance and partners

See [GOVERNANCE.md](../GOVERNANCE.md). The institutions concerned: the Commune of Cotonou (its addressing cell), the ministry carrying the 22 April 2026 strategy, ANDF (land), IGN Bénin (geodesy, base maps), La Poste du Bénin, ASIN (digital services), ANCB (association of communes), APDP (data protection) and the emergency services (112 SAMU, 117 and 116 police, 118 sapeurs-pompiers).

## 13. What is not verified

- Arrondissement outlines come from geoBoundaries (2021), not from an official file. Cotonou's 2nd and 3rd arrondissements are missing from it; the Sô-Ava outlines misplace Ganvié; at the Cotonou and Sèmè-Podji edge it disagrees with the OCHA commune boundary. Because the code area of a compound is fixed in the register, a corrected outline changes no code.
- Arrondissement names were repaired from a file with broken accents and need checking against the law.
- The quartier index is the rank of OpenStreetMap places, not the official list, which is not yet available in machine-readable form.
- 1,300 plate names are provisional until their communes choose (section 2.3).
- The compound grouping is a floor (section 3.2) and the class mix is mostly the default (section 4.2).
- 13,999 compounds whose reference point lies outside every arrondissement outline (mostly along the northern borders of Ségbana, Malanville and Karimama) take the arrondissement of the nearest outline for their spot code (section 5); 158 of them, on the border with Togo and west of every frame, have a spot code that names the frame's edge cell, up to 392 m from the entrance. A corrected outline changes no compound code.
- People never see the check digit, so a mistyped remembered code is caught only when it falls outside the issued numbers of its name: about one error in three. The others name another compound, almost always in the same area, a median 220 m away (`model/stats/evaluation.json`); read-back of the place and the map are the safeguard.
