# Security and data problems

## How to report

Write to **hello@nways.ng** with "Security: open-addresses-benin" in the subject. Please do not open a public issue for a security problem or for anything that exposes personal data.

Say what you found, where (file, endpoint, version or commit), how to reproduce it, and what an attacker or a careless user could do with it. We acknowledge each report, keep you informed until the problem is fixed, and credit reporters who wish to be named.

## What to report

- A flaw in the server (`server/`): a way to issue or change codes without a valid key, to read or corrupt the database, to crash the service, or to get around the daily limit.
- A flaw in the engine (`engine/reference/`) that makes two compounds share a code, accepts a wrong check digit, or decodes a code to the wrong place.
- Personal data in the repository or the registry: a resident's name, a phone number, an identity number, or a photograph of a person. The registry describes places only; any personal data in it is a defect and is removed at once.
- A registry file whose SHA-256 does not match `registry/MANIFEST.json`.

## Running the server safely

- Run a read-only deployment (no `ISSUE_KEYS`) unless you are the designated issuer.
- Serve the API over HTTPS, behind a reverse proxy (`server/README.md`).
- Keep issuing keys secret, one per office or application, and withdraw a key by removing it from `ISSUE_KEYS`.
- Keep the container image and Python up to date, and back up an issuing deployment's database every day.

## Supported versions

Fixes are made on the `main` branch. Deployments should follow it and rebuild after each release of the registry.
