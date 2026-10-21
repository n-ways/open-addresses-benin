# Governance: N-Ways addresses for Benin

The codes were issued on 20 October 2026, and this repository is public.

## Who decides

- **Maintainers.** The N-Ways addressing team for Benin keeps this repository. A change to the engine, the formats or the keys needs the approval of two maintainers and a green test run (`engine/reference/test_bj.py`, `server/tests/`). Any change to `engine/reference/test_vectors.json` or `engine/reference/vectors.json` must be explained in its pull request, because a changed vector is a changed code.
- **Codes are never decided by hand.** Compounds, numbers, profiles and doors are settled by the engine's rules and by the agreement of residents, couriers and visitors, the way N-Ways settles corrections to its map. No code waits in a queue for someone's approval.
- **Official data first.** Where a Beninese authority publishes addresses, they are imported and shown first, exactly as written: the Commune of Cotonou's 2013 plan, the national programme of 22 April 2026 once it delivers, and any successor. Every home keeps its N-Ways code beside the official address, so that every compound, with or without an official address, can be reached the same way.

## One issuer

Codes for Benin are issued by one issuer only. A new home's number depends on every number already issued in its area (`engine/SPEC.md` 5.2), so two issuers working at once would give the same number to two homes. N-WAYS LIMITED issues the codes today. If the State of Benin designates another body as the issuer, the register passes to that body (see "Hand-over"), so that there is still one issuer.

Anyone may run the server in `server/` to serve the published registry. A deployment issues codes only when the State or N-WAYS LIMITED has designated it as the issuer; every other deployment runs read-only and takes new codes from the published registry.

## Stability promises

1. An issued code never moves and is never reused.
2. Renames and re-districting change only the alias table.
3. A change to the engine may not change an issued code.
4. Retired codes stay listed for ever, marked `retired`.

## Disputes

- **Grouping or gate.** A neighbour's dispute over a grouping or a gate suspends confirmation of that compound until the evidence agrees. It does not delete the code.
- **Land.** A code is an address, not a land title. Land disputes belong to the courts and the ANDF, never to this registry. A disputed outline is hidden from the public map until resolved.

## Hand-over

The repository is built to be handed over if the State designates a body to hold the register: the ministry leading the strategy of 22 April 2026, the ANDF, IGN Bénin or La Poste du Bénin are the natural candidates. A hand-over includes the registry, the alias table, the engine, the server and the mapping to the official system. N-Ways would then follow that body's rules.

## Institutions concerned

1. The Commune of Cotonou: its addressing cell and the data of the 2013 plan, through a data-sharing agreement.
2. The ministry leading the national addressing strategy of 2026.
3. The ANDF: parcel cross-references, for the checks of "Ajouter ma maison".
4. IGN Bénin: geodesy and base maps.
5. La Poste du Bénin.
6. ASIN (digital services).
7. ANCB (association of communes).
8. APDP (data protection).
9. The emergency services: 112 SAMU, 117 and 116 police, 118 sapeurs-pompiers.

## Privacy duties

- Declare the processing of personal data to the APDP before it starts (Code du numérique, art. 405).
- Obtain authorisation before hosting personal data abroad (art. 391, 407).
- Never store residents' names, phone numbers or identity numbers with a code.
- Honour requests for a private door.

## Naming

Always "N-Ways address" or "adresse N-Ways". Never "code postal", "official address" or "adresse officielle".
