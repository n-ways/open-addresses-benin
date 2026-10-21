# Benin: existing postal and address systems

Checked 18 October 2026. "Opened" means the page or file was read on that date; "snippet" means it was seen only in a search result and is not relied on alone. Full list in [SOURCES.md](../SOURCES.md).

**Status on 20 October 2026:** no format, firm, platform or timetable of the national strategy of 22 April 2026 has been published (press of 22–23 April, SRTB, Agence Ecofin, Bénin Web TV: no follow-up); Benin still has no postal code; Cotonou's 2013 street codes are carried by 307 ways in OpenStreetMap (extract of 17 October 2026). Data protection: Loi 2017-20 (Code du numérique), APDP.

## Verdict

**Benin has no postal codes.** Mail goes to post-office boxes (boîtes postales, BP) followed by the town. In four cities (Cotonou, Porto-Novo, Abomey and Parakou) a two-digit number in front of "BP" names the post office that holds the box. That number identifies an office, not an area, a street or a door.

**Door-level street addresses exist only in parts of Cotonou,** from the municipal addressing plan begun in 2013. Their signs and painted numbers are incomplete, and no update has been found since 2015. **A national street-and-door system was authorised on 22 April 2026,** but as of 18 October 2026 no format, firm, platform or launch has been published.

So the N-Ways model for Benin must:

- keep the BP box as free text;
- reuse Cotonou's street codes and metric door numbers wherever they exist;
- start every code with a place name, so it cannot be mistaken for the national code the State will issue;
- offer the State a mapping table and a hand-over.

## What exists

| System | Who | State on 18 Oct 2026 | Format | Open data | N-Ways use |
|---|---|---|---|---|---|
| P.O. boxes | La Poste du Bénin S.A. | Live; the only postal addressing | "10 BP 648 / COTONOU": two-digit delivery-office prefix in Cotonou, Porto-Novo, Abomey, Parakou | None | Free-text field on a compound (never a key) |
| Cotonou street addressing (plan d'adressage) | Commune of Cotonou with French cooperation (PA2D), launched 12 Nov 2013 | Legacy, partly signed | Street code = arrondissement + "." + three-digit street number ("Rue 12.217" = 12th arrondissement, street 217). Door number = roughly metres from the start of the street, odd on one side, even on the other ("N° 43, Rue 12.217") | None, no API | Stored on each entrance where known. N-Ways' Cotonou codes carry the same arrondissement number |
| National strategy for standardising street and door addressing | Council of Ministers, 22 Apr 2026, item II-1 (no ministry named) | Plan. A specialised firm is to implement it first in the Grand-Nokoué towns (Abomey-Calavi, Cotonou, Ouidah, Porto-Novo, Sèmè-Podji) and Parakou. No follow-up found May–Oct 2026 | Not published ("numérique et géolocalisé", "participatif") | Not announced | Point to it as soon as it exists. N-Ways offers its compound registry and a mapping table |
| ANDF cadastre / e-Foncier | Agence Nationale du Domaine et du Foncier | Live. Cadastre online since Apr 2019 (16.5% of the territory then). About 491,000 parcels mapped 2021–2025. e-Foncier mandatory for land formalities in 12 communes since 1 Jan 2025 | Parcel references: NUP (numéro unique de parcelle), îlot + parcelle, titre foncier (TF) number. Map in WGS 84 / UTM 31N (EPSG:32631) | Public viewer at cadastre.bj, no download licence | Cross-reference on a compound when the landholder gives it. A parcel is a land right, not an address |
| "Adressage participatif" demonstrator | Private (adressage.up.railway.app) | States it has "no official character" | Proposed street names | No licence | None |
| ANIP / ASIN | Identity and digital agencies | No digital-address product found (ANIP issues a residence certificate) | — | — | Never linked to identity numbers |
| OpenStreetMap | Community, ODbL | 946 house numbers and 932 `addr:street` in the whole country (Overpass, 12 Oct 2026). About 9% of Cotonou's named road ways. 55 `addr:postcode` values, none a real postcode | — | ODbL | Street names, a few Cotonou street codes as `ref` (307 ways with an "NN.NNN" code in central Cotonou, N-Ways extract 17 Oct 2026) |

### La Poste du Bénin and the UPU

The UPU addressing sheet for Benin is footed 11/2025. It gives five address lines with no postcode field: name, P.O. box, locality, telephone, country. It says: "In Cotonou, Porto-Novo, Abomey and Parakou, the delivery post office is identified by two digits, placed to the left of the P.O. box number". Its example is "10 BP 648 / COTONOU". (Opened.)

La Poste du Bénin's website (laposte.bj, opened) mentions no postcode and no digital address. It offers BP fee payment, mail tracking and a "service distribution" page. Commercial postcode vendors list Benin as having no postcode system (snippet).

### Cotonou's 2013 street addressing

La Nouvelle Tribune reported the launch on 12 Nov 2013 (opened):

- Work started on 1 Oct 2013, in the 7th and 12th arrondissements.
- It cost about 330 million F CFA, presented by the PA2D project of the French Embassy.
- Each street gets a "numéro géographique" based on its arrondissement.
- Example: the mayor's house is "N° 43, Rue 12.217".

The OSM wiki for Benin (opened) and an OSM mailing-list message of 3 Sep 2017 (opened) describe the same scheme:

- "12.345" is the 345th street of the 12th arrondissement.
- House numbers are painted in blue and roughly equal the metres from the start of the street.
- Odd numbers are on one side and even on the other.

An AFP report of 2018 says numbers were generally not displayed (SOURCES.md 16; the report was not re-opened for this record). No official progress report after the 2015 "Plan d'adressage de Cotonou" map was found. **Unverified:** how far the plates and painted numbers have spread across the 13 arrondissements.

### The 22 April 2026 decision

The official minutes (sgg.gouv.bj/cm/2026-04-22/, opened) are titled "Elaboration de la stratégie nationale pour la normalisation et l'encadrement de l'adressage des voies et des portes du Bénin":

- The strategy covers "la gestion et l'encadrement de l'adressage des voies et entrées des lieux de vie et d'activité".
- It aims at "un nouveau système d'adressage innovant et participatif, numérique et géolocalisé".
- It authorises "une mission ... avec un cabinet spécialisé" in the Grand-Nokoué towns and Parakou.

No ministry is named. Press coverage on 22–23 April (Bénin Web TV and SRTB opened; Agence Ecofin and others seen as snippets) adds no timeline, budget or format. The Council of Ministers minutes of 7 Oct 2026 (opened) have no addressing item. **Not fully verified:** every set of minutes from May to September 2026 was not read.

### Land parcels (for "Ajouter ma maison" and cross-references)

**Law.** Loi n° 2013-01 du 14 août 2013 portant Code foncier et domanial, amended by Loi n° 2017-15 du 10 août 2017 (opened). Confirmation of land rights ends in a titre foncier (new art. 4). Plans must be checked by an "ingénieur géomètre agréé" (new art. 183). Customary holdings are recognised: attestation de détention coutumière, and the rural plan foncier at the village chief's request (new art. 196).

**ANDF cadastre.** cadastre.bj (opened, its public application code) searches by commune, îlot or TF number. Its parcel fields are `nup, ilot, parcelle, numtf, datetf, quartier, arrondissement, commune, departement, surface`, and its map is EPSG:32631.

**Consequence for N-Ways:**

- A plot outline drawn in the N-Ways app has no legal value. It is an address aid, never a title.
- Survey plans (plans parcellaires) carry UTM 31N beacon coordinates, which the N-Ways engine reads without reprojection.
- **Unverified:** real examples of the written forms ("parcelle B du lot 1234", "TF n° … Cotonou"), and the acronym of the order of surveyors (OGEB).

### Data protection

Loi n° 2017-20 portant Code du numérique, Book V, is enforced by the APDP (Autorité de Protection des Données à caractère Personnel). The APDP-hosted text was opened. Its rules:

- Personal data explicitly includes identification by "données de localisation".
- Every processing needs a prior declaration to the APDP (art. 405), unless a data protection officer is appointed (art. 408; public bodies cannot use that exemption).
- Prior authorisation is needed (art. 407) for, among other things:
  - national ID numbers or similar identifiers;
  - linking files together;
  - transfers to a third state, which need an APDP finding of equivalent protection (art. 391).

APDP's short number is 150 (ARCEP list, June 2026).

## What this means for the design

**Where the State has addresses, they are shown first, exactly as written; every home also has its N-Ways code beside them.** An official address is the one people should see, and a code that every compound has, in one form everywhere, is what lets any service reach any home. The codes were issued on 20 October 2026, one for every compound. In Benin that means:

- Cotonou's official street names and codes are shown first, exactly as written, on every compound within 30 m of a named street ("Rue 12.217, Cotonou"); a door number of the 2013 plan replaces the street as soon as it is known (the Commune of Cotonou's door data is not open; it can be shared under a data-sharing agreement, and meanwhile residents read the number from their plate). The N-Ways code sits beside it.
- The six 2026 pilot towns show the national programme's addresses first when it delivers them; no N-Ways code changes.
- Everywhere else the N-Ways code is the address.

1. **No postal code to point to.** The N-Ways code is not called a postcode and never uses "BP".
2. **Cotonou's arrondissement numbers are already in people's street codes.** Codes in Cotonou carry the same arrondissement number, so "Rue 12.217" and an N-Ways code in the 12th arrondissement agree.
3. **The State's future code.** Its format is unknown. N-Ways codes start with a place name ("Zogbo · 46 17"), so they cannot be mistaken for any numeric code the State issues, and the registry can be handed over or mapped one to one.
4. **Parcels are cross-references only.** They are land rights, not addresses.
5. **Data protection.** Processing personal data needs a prior declaration to the APDP, and hosting it outside Benin needs authorisation. The registry holds places, never people.
6. **Short names already in use.** No published list of short forms of Benin quartier or village names was found (the Loi 2013-05 annex gives the official names only). The plate-name rule (`docs/model.md` section 2.3) therefore asserts no documented short form: every shortened name comes from the rule, and every doubtful one goes to the commune. A short form enters the table (`KNOWN` in `tools/bj_plates.py`) only with a published source, listed in `SOURCES.md`.
