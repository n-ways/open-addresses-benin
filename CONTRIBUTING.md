# Contributing

Corrections and improvements are welcome from anyone: residents, communes, ministries, couriers, researchers and developers. This page says how to propose them and what can and cannot change.

## What can change, and what cannot

- **Issued codes do not change.** A code never moves and its number is never reused (`engine/SPEC.md` 8). A correction to a compound (its grouping, its gate, its use) changes its record, never its code.
- **Names change through aliases.** A commune's choice of a plate name for one of the 1,300 flagged areas, a corrected spelling or an official quartier name is added as an alias; the old form keeps decoding and the numbers stay.
- **The engine may improve, the codes may not.** A change to `engine/reference/` must keep every value in `engine/reference/test_vectors.json` and `engine/reference/vectors.json`. If it cannot, the pull request must say why, and it will be refused if it changes an issued code.
- **The registry is published by the issuer.** Do not edit files in `registry/` by hand: they are exported by the issuer with their checksums in `MANIFEST.json`, and the server refuses a registry that does not match.

## How to propose a change

1. **Open an issue** on GitHub describing the problem: the code or area concerned, what is wrong, and the evidence (a published source, a photo of a plate, a commune decision). For a change to a name, give the source; a short form of a name enters `tools/bj_plates.py` (`KNOWN`) only with a published source listed in `SOURCES.md`.
2. **Send a pull request** for code or documentation. Keep it to one subject. Run the tests first:

   ```sh
   python3 engine/reference/test_bj.py
   python3 -m unittest discover -s server/tests
   ```

3. Two maintainers review and approve a change to the engine, the formats or the keys (`GOVERNANCE.md`).

Write code with the standard library only, for Python 3.9 or newer, in the style of the surrounding files. Comments explain why a rule is what it is; the specification says what it is.

## The issuer rule

New codes are issued by one issuer for the whole of Benin, today N-WAYS LIMITED, or a body the State designates. A new home's number depends on every number already issued in its area, so two issuers would give the same number to two homes. Do not run the server with issuing keys unless your deployment has been designated as the issuer; run it read-only and import the published registry instead ([server/README.md](server/README.md#one-issuer)). To ask for codes for new homes, use the N-Ways app ("Ajouter ma maison") or contact hello@nways.ng.

## Data from public bodies

A commune, a ministry or an agency that holds official addresses, quartier lists or outlines can share them under a data-sharing agreement: write to hello@nways.ng. Official addresses are shown first, exactly as written, and keep their own terms.

## Conduct

Be courteous and precise. Never post personal data (names, phone numbers, identity numbers) in an issue or a pull request: the registry describes places, never people.
