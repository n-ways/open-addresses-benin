# The registry server

A ready-made HTTP service for the N-Ways codes of Benin. It loads the published registry (`registry/`) into a SQLite database and answers the JSON API described in [`docs/api.md`](../docs/api.md) and [`openapi.yaml`](openapi.yaml): look up a code, find what people type, the code at a point, the codes nearby, spot codes, communes and code areas. A deployment designated as the issuer can also issue new codes, by exactly the rules of the N-Ways issuer, so every deployment gives the same answers for the same register.

- Python 3.9 or newer, standard library only. No package to install.
- The address logic is the repository's reference engine (`engine/reference/bj_engine.py`): parsing, check digits, name keys, spot codes and plate names are not reimplemented here.
- Read-only by default. Issuing is switched on only by giving it issuing keys, and only the designated issuer may do that (see "One issuer" below).

## Deploy with Docker

```sh
git clone https://github.com/n-ways/open-addresses-benin.git
cd open-addresses-benin/server
docker compose up -d
curl -s http://localhost:8080/v1/health
```

That is the whole deployment. On first start the container imports the registry bundled in the image into the `addresses` volume: 4,147,741 codes, about a minute and a half on a laptop and about 2.1 GB of disk. It then serves on port 8080. Later starts find the registry already loaded and serve at once. The container runs as an unprivileged user and has a health check on `/v1/health`.

Settings go in the environment, or in a `.env` file next to `docker-compose.yml`:

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8080` | port the service listens on (in compose, the host port) |
| `ADDRESSES_DB` | `/data/addresses.sqlite` in the image, `data/addresses.sqlite` otherwise | the database file |
| `ISSUE_KEYS` | empty | comma-separated bearer keys allowed to issue and change codes; empty means read-only |
| `ISSUE_PER_DAY` | `5` | codes one key may issue in 24 hours (the limit the N-Ways issuer applies to one phone; raise it for an office that registers many homes) |
| `CORS_ORIGINS` | `*` in compose, empty otherwise | origins allowed to call the API from a browser (`*` for any) |
| `HOST` | `0.0.0.0` | address to listen on |

Use long random keys (`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`), one per office or application, so that one can be withdrawn without the others. The server stores only a hash of the key beside each code it issues.

## Run with plain Python

```sh
python3 -m server import --registry registry --db data/addresses.sqlite
python3 -m server serve --db data/addresses.sqlite --port 8080
```

Run both from the repository root. `import` checks every file against `registry/MANIFEST.json` (SHA-256 of the uncompressed bytes, codes per file and in total) and refuses the whole registry on any mismatch, leaving the database as it was. It can be re-run safely: the same registry is not loaded twice, and `--force` reloads it. `python3 -m server start` does both steps (import if needed, then serve) and is what the container runs.

`export` writes the register back in the published format, the same columns in the same order, gzip-compressed, with its `MANIFEST.json`:

```sh
python3 -m server export --db data/addresses.sqlite --out exported/
```

An export of an unchanged import is byte-identical to the published registry once uncompressed, `MANIFEST.json` included. After codes have been issued or changed, the export carries them and their new blocks, with a new manifest. The tests check both.

To run it as a system service without Docker, a systemd unit is enough:

```ini
[Unit]
Description=N-Ways Addressing for Benin
After=network.target

[Service]
User=addresses
WorkingDirectory=/opt/open-addresses-benin
Environment=ADDRESSES_DB=/var/lib/addresses/addresses.sqlite
ExecStart=/usr/bin/python3 -m server start --port 8080
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Behind a reverse proxy with TLS

Serve the API over HTTPS. The server speaks plain HTTP on its port; put a reverse proxy in front for TLS, compression and access logs. With Caddy, which obtains and renews the certificate itself:

```
addresses.example.bj {
    encode gzip
    reverse_proxy 127.0.0.1:8080
}
```

With nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name addresses.example.bj;
    ssl_certificate     /etc/letsencrypt/live/addresses.example.bj/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/addresses.example.bj/privkey.pem;
    gzip on;
    gzip_types application/json;
    client_max_body_size 64k;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

When the proxy runs on the same machine, publish the container port on the loopback interface only (`"127.0.0.1:8080:8080"` in `docker-compose.yml`). Read endpoints send `Cache-Control: public, max-age=60`, so a caching proxy or CDN may hold them for a minute.

## Back up

The database is one SQLite file in WAL mode. Copy it while the server runs with SQLite's online backup, never with a plain file copy:

```sh
sqlite3 /data/addresses.sqlite ".backup '/backup/addresses-$(date +%F).sqlite'"
# or, with Docker:
docker compose exec addresses python3 -c "import sqlite3; s = sqlite3.connect('/data/addresses.sqlite'); d = sqlite3.connect('/data/backup.sqlite'); s.backup(d); d.close()"
```

A read-only deployment needs no backup: the published registry rebuilds it. An issuing deployment must be backed up at least daily, and an `export` kept beside each backup, because the codes it issued exist nowhere else until they are published.

## Update to a newer registry

With Docker, pull the repository and rebuild; the new image carries the new registry and the container imports it on start:

```sh
git pull
docker compose up -d --build
```

Without Docker, `git pull` and run `python3 -m server import` again. The import replaces the published codes with the new ones in a single transaction: the service keeps answering from the old data until the new data is complete. Codes this deployment issued itself are kept, unless the new registry holds the same code or number, in which case the published one wins.

## The API

[`docs/api.md`](../docs/api.md) shows every endpoint with a real request and its real response, errors included; [`openapi.yaml`](openapi.yaml) is the OpenAPI 3.1 description with schemas and examples. In short:

| | |
|---|---|
| `GET /v1/health`, `GET /v1/info` | the service, the registry, licences and credit |
| `GET /v1/codes/{machine}` | the full card of one code |
| `GET /v1/find?q=` | remembered form, machine code, official address or spot code |
| `GET /v1/at?lat=&lng=` | the code at a point (an entrance within 12 m) |
| `GET /v1/near?lat=&lng=&radius=` | codes within up to 500 m |
| `GET /v1/verify?code=` | shape, check digit and issue status of a machine code |
| `GET /v1/spot`, `GET /v1/spot/decode` | spot codes |
| `GET /v1/zones`, `GET /v1/zones/{key}`, `GET /v1/zones/{key}/codes` | communes, their areas, their codes page by page |
| `GET /v1/areas/{id}`, `GET /v1/areas?name=` | code areas |
| `POST /v1/codes`, `PATCH /v1/codes/{machine}` | issue a code; confirm, retire, move its entrance (issuer only) |

## One issuer

**Codes for Benin are issued by one issuer only.** A deployment issues codes only if the State of Benin or N-WAYS LIMITED has designated it as the issuer; every other deployment runs read-only, without `ISSUE_KEYS`.

The reason is arithmetic. A new home takes the free number between its neighbours on its area's curve, or the next number of the area's reserve, or the first number of the next free block of its name. Two issuers working from the same register compute the same "next free" number for two different homes, and the same remembered form ("Cadjéhoun · 40 00") would then name two compounds: the one property the code must never lose. The register stays single by having a single writer. Every other deployment receives the issuer's codes through the published registry (`export` on the issuer, `import` everywhere else) and serves them unchanged.

A designated issuer should also:

- keep the keys for the offices and applications it trusts, and withdraw a key by removing it from `ISSUE_KEYS` and restarting;
- publish its export regularly so that every other deployment stays current;
- keep one database and one running instance. The server serialises issuing inside its process and keeps the area blocks in memory; the unique index on name and number stops a second process from storing the same number twice, but that process would refuse the request instead of issuing the next free number, and a second database would issue the same numbers again.

## How issuing works

The rules are those of `engine/SPEC.md` 5 and 7, applied as the N-Ways issuer applies them.

1. **In Benin.** The border decides (`engine/SPEC.md` 1b): a point more than 300 m outside Benin's national border (OpenStreetMap `admin_level=2`, shipped simplified as `engine/data/border.json`) is in a neighbouring country and is refused with `422 outside_country`, whatever outline or spot frame holds it; an entrance is never moved there either. Within it, the point lies in an arrondissement outline, or, in none (a sliver between outlines, a border river), `engine/SPEC.md` 2.4 gives it a spot code; else the request is refused with `422 outside_country`. `GET /v1/at` uses the same test, so a compound in a gap between outlines is found by point.
2. **Already coded?** A request within 3 m of an issued entrance, or inside or overlapping more than half of an outline issued here, is refused with `409 exists` and the code the building has. The published registry carries entrance points, not building outlines, so these checks use the entrances of published codes and the outlines of codes this deployment issued.
3. **Outline.** An outline, when given, must cover between 6 m² and 2 ha.
4. **Area.** Another door (`of`) takes the area of its compound and must be within 80 m of its entrance. A new compound takes the area of the nearest issued code within 250 m, so that a new house joins its neighbours; failing that, the code area of the point (the nearest place of its arrondissement); failing that, the nearest area.
5. **Number.** Between the new home's neighbours on the area's Hilbert curve, below the tail reserve, the free number nearest their midpoint (the lower first); else the lowest free number of the tail reserve (the top third of the area's first block); else of its later blocks. A retired number is never free again.
6. **Extension block.** When an area is full it takes a new block of its name: the lowest free hundreds above every block of the name, of size max(200, twice its compounds rounded up to hundreds). If the name's range has no room left the request is refused (`409 area_full`); the commune then chooses a qualifier.
7. **The code.** Machine form `BJ-<area>-<number>-<check>`, remembered form `<plate name> <number>`, written form `<plate name> · <number in pairs>`; status `provisional`, issued `on-demand`. New blocks are stored and appear in `/v1/areas` and in `export`.

`server/tests/test_server.py` proves this against the N-Ways issuer: `server/testdata/parity.json` holds the numbers, codes and blocks the N-Ways issuer gave 530 new homes and doors in ten areas of Covè (two of them filled until they took extension blocks), and the code area, nearest area, spot code and Plus Code of 400 points; the server reproduces every one, and replays the 434 doors through `POST /v1/codes` with the same results. `server/testdata/gaps.csv` holds 30 published compounds of Athiémé, Karimama and Ouaké whose entrances lie in no arrondissement outline: `GET /v1/at` finds each with its own code, as the N-Ways issuer does, a free point among them is issued a code, and points that have no spot code are refused. Run the tests from the repository root:

```sh
python3 -m unittest discover -s server/tests
```

The fixture in `server/testdata/registry/` is the published area table and the real codes of the commune of Covè, with their manifest.

## Limits

- Lookups by point use the entrance of each code. The published registry does not carry building outlines, so a point inside a large building but more than 12 m from its entrance is answered `none` here, where the N-Ways service, which holds the outlines, answers `found`.
- People's confirmations ("this code is right", "the gate is elsewhere") are gathered by the N-Ways app and settle a code's status there; this server takes status changes and entrance moves from its issuing keys instead, and logs each one in the `changes` table.
- The database for the whole country is about 2.1 GB; allow 5 GB of free disk for an import (the write-ahead log holds a second copy until the import is complete).
