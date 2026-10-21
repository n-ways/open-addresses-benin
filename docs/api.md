# The registry API

Every example on this page is a real request to the server in `server/`, loaded with the published registry (`registry/`, 4,147,741 codes), and the response it gave, copied unedited except where long lists are cut (marked "lists shortened"). The machine-readable description is [`server/openapi.yaml`](../server/openapi.yaml); how to deploy the server is in [`server/README.md`](../server/README.md).

- Base path: `/v1`. Responses are JSON (`application/json; charset=utf-8`), field names in `snake_case`, and stable: a field may be added, none is renamed or removed.
- Errors: `{"error": {"code": "...", "message": "..."}}` with the HTTP status that matches (400 a malformed request, 401/403 a missing or refused key, 404 nothing found, 405 a method the endpoint does not take, 409 a conflict with the register, 422 a well-formed request the rules refuse, 429 the daily limit). `code` is stable and meant for programs; `message` is plain English for people.
- Coordinates are WGS 84 decimal degrees. Distances are metres.
- People never see a check digit: the written and spoken forms have none. The machine form carries it, for systems.
- Reading needs no key. Issuing and changing codes needs a bearer key and is enabled only on the designated issuer.

In the examples the server runs at `https://addresses.example.bj`.

| Endpoint | What it answers |
|---|---|
| `GET /v1/health` | is the service up, and which registry it serves |
| `GET /v1/info` | country, counts, licences, credit line, whether it issues |
| `GET /v1/codes/{machine}` | the full card of one code |
| `GET /v1/find?q=` | whatever people type: remembered form, machine code, official address, spot code |
| `GET /v1/at?lat=&lng=` | the code of the compound at a point |
| `GET /v1/near?lat=&lng=&radius=` | the codes around a point |
| `GET /v1/verify?code=` | is this machine code valid and issued |
| `GET /v1/spot?lat=&lng=`, `GET /v1/spot/decode?code=` | spot code of any point, and back |
| `GET /v1/zones`, `GET /v1/zones/{key}` | the communes, and one commune with its areas |
| `GET /v1/zones/{key}/codes?after=&limit=` | every code of a commune, page by page |
| `GET /v1/areas/{id}`, `GET /v1/areas?name=` | a code area, or the areas of a name |
| `POST /v1/codes` | issue a code for a new compound or another door (issuer only) |
| `PATCH /v1/codes/{machine}` | confirm, retire, or move the entrance of a code (issuer only) |

## Service

### GET /v1/health

Liveness and the registry in service. Use it for load-balancer and container health checks.

```sh
curl -s 'https://addresses.example.bj/v1/health'
```

`200 OK`

```json
{
  "status": "ok",
  "country": "BJ",
  "codes": 4147741,
  "registry_exported": "2026-10-20T19:51:08Z"
}
```

### GET /v1/info

The country, the counts, the licences and the credit line every reuse must show, and whether this deployment issues codes.

```sh
curl -s 'https://addresses.example.bj/v1/info'
```

`200 OK`

```json
{
  "country": "BJ",
  "name": "Benin",
  "codes": {
    "total": 4147741,
    "by_status": {
      "provisional": 4147741
    }
  },
  "zones": 77,
  "areas": 12964,
  "zone_kind": "commune",
  "area_kind": "quartier or village",
  "registry": {
    "exported": "2026-10-20T19:51:08Z",
    "imported_at": "2026-10-21T13:39:29Z",
    "codes": 4147741,
    "local_changes": false
  },
  "issuing": {
    "enabled": false,
    "per_key_per_day": 5
  },
  "engine": "internal/addressing/bj (SPEC v1.0)",
  "spec": "engine/SPEC.md 1.0",
  "spatial_index": "rtree",
  "licences": {
    "data": "ODbL 1.0 (LICENSE-DATA)",
    "code": "Apache License 2.0 (LICENSE, NOTICE)",
    "documents": "CC BY 4.0 (LICENSE-DOCS)"
  },
  "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)",
  "credit_url": "https://github.com/n-ways/open-addresses-benin"
}
```

## Codes

### GET /v1/codes/{machine}

The full card of one code. `registry` repeats the published row exactly as written in `registry/<commune>.csv.gz`; the other fields are the same values typed and named, plus the forms people use (`written`, `spoken`), what to show first (`display`: the official address where the State has one, else the written form), the spot code and Plus Code of the entrance, and the code area. The check digit may be left off (`BJ-COT-12-001-1807`); a wrong one is refused, never corrected.

```sh
curl -s 'https://addresses.example.bj/v1/codes/BJ-COT-12-001-1807-4'
```

`200 OK`

```json
{
  "machine": "BJ-COT-12-001-1807-4",
  "home": "Cadjéhoun 1807",
  "written": "Cadjéhoun · 18 07",
  "spoken": "Cadjéhoun, 18 07",
  "display": "Rue 12.202, Cotonou",
  "zone": "COT-12-001",
  "number": 1807,
  "check": 4,
  "status": "provisional",
  "issued": "bulk",
  "issued_at": "2026-10-20T19:40:43Z",
  "entrance": {
    "lat": 6.3582212,
    "lng": 2.3911161,
    "kind": "centre"
  },
  "spot_code": "COT 12 · 35G 2PX",
  "plus_code": "6FR4995R+7CQ",
  "official_address": "Rue 12.202, Cotonou",
  "official_name": "Cadjéhoun",
  "area": {
    "zone": "COT-12-001",
    "id": 5664,
    "plate_name": "Cadjéhoun",
    "official_name": "Cadjéhoun",
    "provisional_name": false,
    "commune_key": "COT",
    "commune": "Cotonou",
    "arrondissement": "12ème Arrondissement",
    "departement": "Littoral"
  },
  "profile": {
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floor_area_m2": 280.6,
    "rule": "single",
    "estate": null
  },
  "registry": {
    "machine": "BJ-COT-12-001-1807-4",
    "home": "Cadjéhoun 1807",
    "written": "Cadjéhoun · 18 07",
    "zone": "COT-12-001",
    "official_name": "Cadjéhoun",
    "number": "1807",
    "check": "4",
    "status": "provisional",
    "issued": "bulk",
    "issued_at": "2026-10-20T19:40:43Z",
    "entrance_lat": "6.3582212",
    "entrance_lng": "2.3911161",
    "entrance_kind": "centre",
    "spot_code": "COT 12 · 35G 2PX",
    "official_address": "Rue 12.202, Cotonou",
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "280.6",
    "rule": "single",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
}
```

A wrong check digit:

```sh
curl -s 'https://addresses.example.bj/v1/codes/BJ-COT-12-001-1807-5'
```

`422 Unprocessable Entity`

```json
{
  "error": {
    "code": "check_digit",
    "message": "The check digit does not match: a digit is wrong or two are swapped."
  }
}
```

A well-formed code that no home has (4000 is in the tail reserve of Cadjéhoun):

```sh
curl -s 'https://addresses.example.bj/v1/codes/BJ-COT-12-001-4000'
```

`404 Not Found`

```json
{
  "error": {
    "code": "not_issued",
    "message": "BJ-COT-12-001-4000-4 is a valid code shape but no home has it."
  }
}
```

A malformed code:

```sh
curl -s 'https://addresses.example.bj/v1/codes/BJ-COT-12-1807'
```

`400 Bad Request`

```json
{
  "error": {
    "code": "invalid_code",
    "message": "Not an N-Ways Benin machine code: expected BJ-CCC-AA-QQQ-NNNN-K."
  }
}
```

### GET /v1/find?q=

One box for everything people type: a remembered or written code in any spacing, case or accents (`Cadjéhoun 18 07`, `cadjehoun 1807`, `CADJÉHOUN · 1807`), optionally followed by the commune after a comma; a machine code; an official address exactly as the State writes it (`Rue 12.202, Cotonou`); or a spot code. `kind` says how the query was read. A commune after the comma must be the right one: it confirms, it never chooses. An official address matches every compound on that street (`count`), returned `limit` at a time (default 20, at most 100).

```sh
curl -s 'https://addresses.example.bj/v1/find?q=cadjehoun%2018%2007%2C%20Cotonou'
```

`200 OK`

```json
{
  "query": "cadjehoun 18 07, Cotonou",
  "kind": "remembered",
  "count": 1,
  "more": false,
  "matches": [
    {
      "machine": "BJ-COT-12-001-1807-4",
      "home": "Cadjéhoun 1807",
      "written": "Cadjéhoun · 18 07",
      "spoken": "Cadjéhoun, 18 07",
      "display": "Rue 12.202, Cotonou",
      "zone": "COT-12-001",
      "number": 1807,
      "check": 4,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T19:40:43Z",
      "entrance": {
        "lat": 6.3582212,
        "lng": 2.3911161,
        "kind": "centre"
      },
      "spot_code": "COT 12 · 35G 2PX",
      "plus_code": "6FR4995R+7CQ",
      "official_address": "Rue 12.202, Cotonou",
      "official_name": "Cadjéhoun",
      "area": {
        "zone": "COT-12-001",
        "id": 5664,
        "plate_name": "Cadjéhoun",
        "official_name": "Cadjéhoun",
        "provisional_name": false,
        "commune_key": "COT",
        "commune": "Cotonou",
        "arrondissement": "12ème Arrondissement",
        "departement": "Littoral"
      },
      "profile": {
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floor_area_m2": 280.6,
        "rule": "single",
        "estate": null
      },
      "registry": {
        "machine": "BJ-COT-12-001-1807-4",
        "home": "Cadjéhoun 1807",
        "written": "Cadjéhoun · 18 07",
        "zone": "COT-12-001",
        "official_name": "Cadjéhoun",
        "number": "1807",
        "check": "4",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T19:40:43Z",
        "entrance_lat": "6.3582212",
        "entrance_lng": "2.3911161",
        "entrance_kind": "centre",
        "spot_code": "COT 12 · 35G 2PX",
        "official_address": "Rue 12.202, Cotonou",
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "280.6",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
    }
  ]
}
```

An official address:

```sh
curl -s 'https://addresses.example.bj/v1/find?q=Rue%2012.202%2C%20Cotonou&limit=1'
```

`200 OK`

```json
{
  "query": "Rue 12.202, Cotonou",
  "kind": "official_address",
  "count": 26,
  "more": true,
  "matches": [
    {
      "machine": "BJ-COT-12-001-1671-4",
      "home": "Cadjéhoun 1671",
      "written": "Cadjéhoun · 16 71",
      "spoken": "Cadjéhoun, 16 71",
      "display": "Rue 12.202, Cotonou",
      "zone": "COT-12-001",
      "number": 1671,
      "check": 4,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T19:40:43Z",
      "entrance": {
        "lat": 6.3608237,
        "lng": 2.3945469,
        "kind": "centre"
      },
      "spot_code": "COT 12 · 35Q 9G8",
      "plus_code": "6FR4996V+8RF",
      "official_address": "Rue 12.202, Cotonou",
      "official_name": "Cadjéhoun",
      "area": {
        "zone": "COT-12-001",
        "id": 5664,
        "plate_name": "Cadjéhoun",
        "official_name": "Cadjéhoun",
        "provisional_name": false,
        "commune_key": "COT",
        "commune": "Cotonou",
        "arrondissement": "12ème Arrondissement",
        "departement": "Littoral"
      },
      "profile": {
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floor_area_m2": 162.8,
        "rule": "single",
        "estate": null
      },
      "registry": {
        "machine": "BJ-COT-12-001-1671-4",
        "home": "Cadjéhoun 1671",
        "written": "Cadjéhoun · 16 71",
        "zone": "COT-12-001",
        "official_name": "Cadjéhoun",
        "number": "1671",
        "check": "4",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T19:40:43Z",
        "entrance_lat": "6.3608237",
        "entrance_lng": "2.3945469",
        "entrance_kind": "centre",
        "spot_code": "COT 12 · 35Q 9G8",
        "official_address": "Rue 12.202, Cotonou",
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "162.8",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
    }
  ]
}
```

A spot code on a compound:

```sh
curl -s 'https://addresses.example.bj/v1/find?q=COT%2012%20%C2%B7%2035G%202PX'
```

`200 OK` (lists shortened)

```json
{
  "query": "COT 12 · 35G 2PX",
  "kind": "spot",
  "count": 1,
  "more": false,
  "matches": [
    {
      "machine": "BJ-COT-12-001-1807-4",
      "home": "Cadjéhoun 1807",
      "written": "Cadjéhoun · 18 07",
      "spoken": "Cadjéhoun, 18 07",
      "display": "Rue 12.202, Cotonou",
      "zone": "COT-12-001",
      "number": 1807,
      "check": 4,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T19:40:43Z",
      "entrance": {
        "lat": 6.3582212,
        "lng": 2.3911161,
        "kind": "centre"
      },
      "spot_code": "COT 12 · 35G 2PX",
      "plus_code": "6FR4995R+7CQ",
      "official_address": "Rue 12.202, Cotonou",
      "official_name": "Cadjéhoun",
      "area": {
        "zone": "COT-12-001",
        "id": 5664,
        "plate_name": "Cadjéhoun",
        "official_name": "Cadjéhoun",
        "provisional_name": false,
        "commune_key": "COT",
        "commune": "Cotonou",
        "arrondissement": "12ème Arrondissement",
        "departement": "Littoral"
      },
      "profile": {
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floor_area_m2": 280.6,
        "rule": "single",
        "estate": null
      },
      "registry": {
        "machine": "BJ-COT-12-001-1807-4",
        "home": "Cadjéhoun 1807",
        "written": "Cadjéhoun · 18 07",
        "zone": "COT-12-001",
        "official_name": "Cadjéhoun",
        "number": "1807",
        "check": "4",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T19:40:43Z",
        "entrance_lat": "6.3582212",
        "entrance_lng": "2.3911161",
        "entrance_kind": "centre",
        "spot_code": "COT 12 · 35G 2PX",
        "official_address": "Rue 12.202, Cotonou",
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "280.6",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
    }
  ]
}
```

The wrong commune:

```sh
curl -s 'https://addresses.example.bj/v1/find?q=Cadj%C3%A9houn%2018%2007%2C%20Abomey'
```

`404 Not Found`

```json
{
  "error": {
    "code": "wrong_commune",
    "message": "Cadjéhoun 18 07 is in Cotonou, not Abomey."
  }
}
```

A number in the spare space of a name (never issued):

```sh
curl -s 'https://addresses.example.bj/v1/find?q=Agata%2045%2000'
```

`404 Not Found`

```json
{
  "error": {
    "code": "not_issued",
    "message": "Agata 45 00 is not issued: no area of that name holds this number."
  }
}
```

A machine code with a wrong check digit:

```sh
curl -s 'https://addresses.example.bj/v1/find?q=BJ-COT-12-001-1807-7'
```

`422 Unprocessable Entity`

```json
{
  "error": {
    "code": "check_digit",
    "message": "The check digit does not match: a digit is wrong or two are swapped."
  }
}
```

A name no area has:

```sh
curl -s 'https://addresses.example.bj/v1/find?q=Kpakpakpa%201234'
```

`404 Not Found`

```json
{
  "error": {
    "code": "unknown_name",
    "message": "No N-Ways area of Benin is called \"Kpakpakpa\"."
  }
}
```

## Places

### GET /v1/at?lat=&lng=

The code of the compound at a point: `found` when an entrance lies within 12 m, with the distance; otherwise `none`, with the code area a new code there would join. Retired codes are never found by point. A point is in Benin when it lies in an arrondissement outline, or, in none (a sliver between outlines, a border river), when `engine/SPEC.md` 2.4 gives it a spot code: the compounds there are found and can be issued like any other, and the area a new code there would join follows the rules of `POST /v1/codes`. A point farther away, or more than 300 m outside Benin's national border whatever outline holds it (`engine/SPEC.md` 1b), is outside Benin (`404 outside_country`).

```sh
curl -s 'https://addresses.example.bj/v1/at?lat=6.35825&lng=2.39112'
```

`200 OK`

```json
{
  "status": "found",
  "distance_m": 3,
  "code": {
    "machine": "BJ-COT-12-001-1807-4",
    "home": "Cadjéhoun 1807",
    "written": "Cadjéhoun · 18 07",
    "spoken": "Cadjéhoun, 18 07",
    "display": "Rue 12.202, Cotonou",
    "zone": "COT-12-001",
    "number": 1807,
    "check": 4,
    "status": "provisional",
    "issued": "bulk",
    "issued_at": "2026-10-20T19:40:43Z",
    "entrance": {
      "lat": 6.3582212,
      "lng": 2.3911161,
      "kind": "centre"
    },
    "spot_code": "COT 12 · 35G 2PX",
    "plus_code": "6FR4995R+7CQ",
    "official_address": "Rue 12.202, Cotonou",
    "official_name": "Cadjéhoun",
    "area": {
      "zone": "COT-12-001",
      "id": 5664,
      "plate_name": "Cadjéhoun",
      "official_name": "Cadjéhoun",
      "provisional_name": false,
      "commune_key": "COT",
      "commune": "Cotonou",
      "arrondissement": "12ème Arrondissement",
      "departement": "Littoral"
    },
    "profile": {
      "class": "residential",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floor_area_m2": 280.6,
      "rule": "single",
      "estate": null
    },
    "registry": {
      "machine": "BJ-COT-12-001-1807-4",
      "home": "Cadjéhoun 1807",
      "written": "Cadjéhoun · 18 07",
      "zone": "COT-12-001",
      "official_name": "Cadjéhoun",
      "number": "1807",
      "check": "4",
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T19:40:43Z",
      "entrance_lat": "6.3582212",
      "entrance_lng": "2.3911161",
      "entrance_kind": "centre",
      "spot_code": "COT 12 · 35G 2PX",
      "official_address": "Rue 12.202, Cotonou",
      "class": "residential",
      "use": "residential",
      "kind": "building",
      "structures": "1",
      "floor_area_m2": "280.6",
      "rule": "single",
      "estate": ""
    },
    "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
  },
  "area": {
    "zone": "COT-12-001",
    "id": 5664,
    "plate_name": "Cadjéhoun",
    "official_name": "Cadjéhoun",
    "provisional_name": false,
    "commune_key": "COT",
    "commune": "Cotonou",
    "arrondissement": "12ème Arrondissement",
    "departement": "Littoral"
  }
}
```

A point with no compound:

```sh
curl -s 'https://addresses.example.bj/v1/at?lat=6.3600&lng=2.3870'
```

`200 OK`

```json
{
  "status": "none",
  "can_issue": false,
  "area": {
    "zone": "COT-13-003",
    "id": 5674,
    "plate_name": "Aïbatin",
    "official_name": "Aïbatin",
    "provisional_name": false,
    "commune_key": "COT",
    "commune": "Cotonou",
    "arrondissement": "13ème Arrondissement",
    "departement": "Littoral"
  }
}
```

A point outside Benin (at sea):

```sh
curl -s 'https://addresses.example.bj/v1/at?lat=6.0&lng=2.4'
```

`404 Not Found`

```json
{
  "error": {
    "code": "outside_country",
    "message": "That point is outside Benin."
  }
}
```

### GET /v1/near?lat=&lng=&radius=&limit=

The codes whose entrances lie within `radius` metres (default 100, at most 500), nearest first, `limit` at a time (default 20, at most 100). `more` says whether the radius holds more.

```sh
curl -s 'https://addresses.example.bj/v1/near?lat=6.35825&lng=2.39112&radius=25&limit=2'
```

`200 OK`

```json
{
  "lat": 6.35825,
  "lng": 2.39112,
  "radius_m": 25.0,
  "count": 2,
  "more": false,
  "codes": [
    {
      "distance_m": 3.2,
      "code": {
        "machine": "BJ-COT-12-001-1807-4",
        "home": "Cadjéhoun 1807",
        "written": "Cadjéhoun · 18 07",
        "spoken": "Cadjéhoun, 18 07",
        "display": "Rue 12.202, Cotonou",
        "zone": "COT-12-001",
        "number": 1807,
        "check": 4,
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T19:40:43Z",
        "entrance": {
          "lat": 6.3582212,
          "lng": 2.3911161,
          "kind": "centre"
        },
        "spot_code": "COT 12 · 35G 2PX",
        "plus_code": "6FR4995R+7CQ",
        "official_address": "Rue 12.202, Cotonou",
        "official_name": "Cadjéhoun",
        "area": {
          "zone": "COT-12-001",
          "id": 5664,
          "plate_name": "Cadjéhoun",
          "official_name": "Cadjéhoun",
          "provisional_name": false,
          "commune_key": "COT",
          "commune": "Cotonou",
          "arrondissement": "12ème Arrondissement",
          "departement": "Littoral"
        },
        "profile": {
          "class": "residential",
          "use": "residential",
          "kind": "building",
          "structures": 1,
          "floor_area_m2": 280.6,
          "rule": "single",
          "estate": null
        },
        "registry": {
          "machine": "BJ-COT-12-001-1807-4",
          "home": "Cadjéhoun 1807",
          "written": "Cadjéhoun · 18 07",
          "zone": "COT-12-001",
          "official_name": "Cadjéhoun",
          "number": "1807",
          "check": "4",
          "status": "provisional",
          "issued": "bulk",
          "issued_at": "2026-10-20T19:40:43Z",
          "entrance_lat": "6.3582212",
          "entrance_lng": "2.3911161",
          "entrance_kind": "centre",
          "spot_code": "COT 12 · 35G 2PX",
          "official_address": "Rue 12.202, Cotonou",
          "class": "residential",
          "use": "residential",
          "kind": "building",
          "structures": "1",
          "floor_area_m2": "280.6",
          "rule": "single",
          "estate": ""
        },
        "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
      }
    },
    {
      "distance_m": 21.7,
      "code": {
        "machine": "BJ-COT-12-001-1808-2",
        "home": "Cadjéhoun 1808",
        "written": "Cadjéhoun · 18 08",
        "spoken": "Cadjéhoun, 18 08",
        "display": "Rue 12.200, Cotonou",
        "zone": "COT-12-001",
        "number": 1808,
        "check": 2,
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T19:40:43Z",
        "entrance": {
          "lat": 6.3583171,
          "lng": 2.3913045,
          "kind": "centre"
        },
        "spot_code": "COT 12 · 35G 3V8",
        "plus_code": "6FR4995R+8GF",
        "official_address": "Rue 12.200, Cotonou",
        "official_name": "Cadjéhoun",
        "area": {
          "zone": "COT-12-001",
          "id": 5664,
          "plate_name": "Cadjéhoun",
          "official_name": "Cadjéhoun",
          "provisional_name": false,
          "commune_key": "COT",
          "commune": "Cotonou",
          "arrondissement": "12ème Arrondissement",
          "departement": "Littoral"
        },
        "profile": {
          "class": "residential",
          "use": "residential",
          "kind": "building",
          "structures": 1,
          "floor_area_m2": 230.0,
          "rule": "single",
          "estate": null
        },
        "registry": {
          "machine": "BJ-COT-12-001-1808-2",
          "home": "Cadjéhoun 1808",
          "written": "Cadjéhoun · 18 08",
          "zone": "COT-12-001",
          "official_name": "Cadjéhoun",
          "number": "1808",
          "check": "2",
          "status": "provisional",
          "issued": "bulk",
          "issued_at": "2026-10-20T19:40:43Z",
          "entrance_lat": "6.3583171",
          "entrance_lng": "2.3913045",
          "entrance_kind": "centre",
          "spot_code": "COT 12 · 35G 3V8",
          "official_address": "Rue 12.200, Cotonou",
          "class": "residential",
          "use": "residential",
          "kind": "building",
          "structures": "1",
          "floor_area_m2": "230.0",
          "rule": "single",
          "estate": ""
        },
        "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
      }
    }
  ]
}
```

A radius over 500 m:

```sh
curl -s 'https://addresses.example.bj/v1/near?lat=6.35825&lng=2.39112&radius=800'
```

`400 Bad Request`

```json
{
  "error": {
    "code": "bad_parameter",
    "message": "radius is in metres, at most 500."
  }
}
```

### GET /v1/verify?code=

Checks a machine code without returning the card: its shape, its check digit and whether it is issued. Always `200` with a verdict, so a form can validate as people type.

```sh
curl -s 'https://addresses.example.bj/v1/verify?code=BJ-COT-12-001-1807-4'
```

`200 OK`

```json
{
  "code": "BJ-COT-12-001-1807-4",
  "valid": true,
  "syntax": true,
  "check_digit": "ok",
  "issued": true,
  "status": "provisional",
  "machine": "BJ-COT-12-001-1807-4",
  "zone": "COT-12-001",
  "reason": null
}
```

Two digits swapped:

```sh
curl -s 'https://addresses.example.bj/v1/verify?code=BJ-COT-12-001-1870-4'
```

`200 OK`

```json
{
  "code": "BJ-COT-12-001-1870-4",
  "valid": false,
  "syntax": true,
  "check_digit": "wrong",
  "issued": false,
  "status": null,
  "machine": null,
  "zone": null,
  "reason": "The check digit does not match: a digit is wrong or two are swapped."
}
```

The check digit left off:

```sh
curl -s 'https://addresses.example.bj/v1/verify?code=BJ-COT-12-001-1807'
```

`200 OK`

```json
{
  "code": "BJ-COT-12-001-1807",
  "valid": false,
  "syntax": true,
  "check_digit": "missing",
  "issued": true,
  "status": "provisional",
  "machine": "BJ-COT-12-001-1807-4",
  "zone": "COT-12-001",
  "reason": "The check digit is missing: the full code is BJ-COT-12-001-1807-4."
}
```

### GET /v1/spot?lat=&lng= and GET /v1/spot/decode?code=

Spot codes name any point of Benin to a 3 m cell of UTM zone 31N, framed by its arrondissement (`engine/SPEC.md` 2). A point in no arrondissement outline (a sliver between outlines, a border river) takes the arrondissement with the nearest outline within 10 km whose frame holds it, ties to the lower commune key and number, or else the nearest cell of a frame at most 999 m away (`engine/SPEC.md` 2.4); a point farther away is outside Benin (`404 outside_country`). `decode` returns the centre of the cell, in the frame of the arrondissement the code names.

```sh
curl -s 'https://addresses.example.bj/v1/spot?lat=6.3582212&lng=2.3911161'
```

`200 OK`

```json
{
  "spot_code": "COT 12 · 35G 2PX",
  "machine": "BJ-COT-12-S-35G2PX",
  "commune": "Cotonou",
  "arrondissement": "12ème Arrondissement",
  "cell_m": 3.0,
  "centre": {
    "lat": 6.3582256,
    "lng": 2.3911096
  }
}
```

```sh
curl -s 'https://addresses.example.bj/v1/spot/decode?code=COT%2012%20%C2%B7%2035G%202PX'
```

`200 OK`

```json
{
  "spot_code": "COT 12 · 35G 2PX",
  "machine": "BJ-COT-12-S-35G2PX",
  "commune": "Cotonou",
  "arrondissement": "12ème Arrondissement",
  "cell_m": 3.0,
  "centre": {
    "lat": 6.3582256,
    "lng": 2.3911096
  }
}
```

A compound of Monsey, Karimama, 1.4 km beyond the arrondissement outline:

```sh
curl -s 'https://addresses.example.bj/v1/spot?lat=12.2796011&lng=2.9817464'
```

`200 OK`

```json
{
  "spot_code": "KAR 05 · 349 RVMVH",
  "machine": "BJ-KAR-05-S-349RVMVH",
  "commune": "Karimama",
  "arrondissement": "Monsey",
  "cell_m": 3.0,
  "centre": {
    "lat": 12.2796078,
    "lng": 2.9817418
  }
}
```

A spot code with characters missing:

```sh
curl -s 'https://addresses.example.bj/v1/spot/decode?code=COT%2012%20%C2%B7%2035G'
```

`400 Bad Request`

```json
{
  "error": {
    "code": "invalid_spot",
    "message": "Spot code here has 6 characters."
  }
}
```

## Communes and areas

A zone is a commune: the registry has one file per commune (`COT.csv.gz` is Cotonou). An area is a code area: a quartier or village, the name in the code.

### GET /v1/zones and GET /v1/zones/{key}

```sh
curl -s 'https://addresses.example.bj/v1/zones'
```

`200 OK` (lists shortened)

```json
{
  "count": 77,
  "zones": [
    {
      "key": "ABO",
      "name": "Abomey",
      "departement": "Zou",
      "areas": 180,
      "codes": 62476,
      "file": "ABO.csv.gz"
    },
    {
      "key": "ADA",
      "name": "Adjarra",
      "departement": "Oueme",
      "areas": 55,
      "codes": 56677,
      "file": "ADA.csv.gz"
    },
    … 75 more
  ]
}
```

```sh
curl -s 'https://addresses.example.bj/v1/zones/COT'
```

`200 OK` (lists shortened)

```json
{
  "key": "COT",
  "name": "Cotonou",
  "departement": "Littoral",
  "codes": 104101,
  "file": "COT.csv.gz",
  "areas": [
    {
      "zone": "COT-01-001",
      "id": 5604,
      "plate_name": "Avotrou",
      "official_name": "Avotrou",
      "provisional_name": false,
      "commune_key": "COT",
      "commune": "Cotonou",
      "arrondissement": "1er Arrondissement",
      "departement": "Littoral",
      "blocks": [
        [
          1000,
          4399
        ]
      ],
      "codes": 1685
    },
    {
      "zone": "COT-01-002",
      "id": 5605,
      "plate_name": "Dandji",
      "official_name": "Dandji",
      "provisional_name": false,
      "commune_key": "COT",
      "commune": "Cotonou",
      "arrondissement": "1er Arrondissement",
      "departement": "Littoral",
      "blocks": [
        [
          1000,
          5099
        ]
      ],
      "codes": 2017
    },
    … 70 more
  ]
}
```

An unknown commune key:

```sh
curl -s 'https://addresses.example.bj/v1/zones/XYZ'
```

`404 Not Found`

```json
{
  "error": {
    "code": "unknown_zone",
    "message": "There is no commune with key XYZ."
  }
}
```

### GET /v1/zones/{key}/codes?after=&limit=

Every code of a commune in machine-code order, `limit` at a time (default 100, at most 1,000). Pass the `next` value as `after` to continue; `next` is `null` on the last page.

```sh
curl -s 'https://addresses.example.bj/v1/zones/COT/codes?limit=1'
```

`200 OK`

```json
{
  "zone": "COT",
  "count": 1,
  "codes": [
    {
      "machine": "BJ-COT-01-001-1000-3",
      "home": "Avotrou 1000",
      "written": "Avotrou · 10 00",
      "spoken": "Avotrou, 10 00",
      "display": "Avotrou · 10 00",
      "zone": "COT-01-001",
      "number": 1000,
      "check": 3,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T19:40:33Z",
      "entrance": {
        "lat": 6.3754826,
        "lng": 2.470778,
        "kind": "centre"
      },
      "spot_code": "COT 01 · 534 69G",
      "plus_code": "6FR49FGC+58R",
      "official_address": null,
      "official_name": "Avotrou",
      "area": {
        "zone": "COT-01-001",
        "id": 5604,
        "plate_name": "Avotrou",
        "official_name": "Avotrou",
        "provisional_name": false,
        "commune_key": "COT",
        "commune": "Cotonou",
        "arrondissement": "1er Arrondissement",
        "departement": "Littoral"
      },
      "profile": {
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floor_area_m2": 33.4,
        "rule": "single",
        "estate": null
      },
      "registry": {
        "machine": "BJ-COT-01-001-1000-3",
        "home": "Avotrou 1000",
        "written": "Avotrou · 10 00",
        "zone": "COT-01-001",
        "official_name": "Avotrou",
        "number": "1000",
        "check": "3",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T19:40:33Z",
        "entrance_lat": "6.3754826",
        "entrance_lng": "2.4707780",
        "entrance_kind": "centre",
        "spot_code": "COT 01 · 534 69G",
        "official_address": "",
        "class": "residential",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "33.4",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
    }
  ],
  "next": "BJ-COT-01-001-1000-3"
}
```

A page over the limit:

```sh
curl -s 'https://addresses.example.bj/v1/zones/COT/codes?limit=5000'
```

`400 Bad Request`

```json
{
  "error": {
    "code": "bad_parameter",
    "message": "limit is at most 1000."
  }
}
```

### GET /v1/areas/{id} and GET /v1/areas?name=

An area by its key (`COT-12-001`) or numeric id, with its blocks, counts and the other areas that share its name. `?name=` takes a plate name or an official name in any case or accents, and the official names that are aliases of a plate name.

```sh
curl -s 'https://addresses.example.bj/v1/areas/COT-12-001'
```

`200 OK`

```json
{
  "zone": "COT-12-001",
  "id": 5664,
  "plate_name": "Cadjéhoun",
  "official_name": "Cadjéhoun",
  "provisional_name": false,
  "commune_key": "COT",
  "commune": "Cotonou",
  "arrondissement": "12ème Arrondissement",
  "departement": "Littoral",
  "name_key": "cajehoun",
  "name_index": 2362,
  "digits": 4,
  "blocks": [
    [
      1000,
      5099
    ]
  ],
  "place": {
    "lat": 6.358485,
    "lng": 2.395116
  },
  "frame": [
    2.389926,
    6.354647,
    2.405961,
    6.367091
  ],
  "codes": {
    "total": 2046,
    "by_status": {
      "provisional": 2046
    }
  },
  "numbers": {
    "lowest": 1000,
    "highest": 3045
  },
  "same_name": []
}
```

```sh
curl -s 'https://addresses.example.bj/v1/areas?name=agata'
```

`200 OK` (lists shortened)

```json
{
  "name": "agata",
  "count": 3,
  "areas": [
    {
      "zone": "ALL-06-001",
      "id": 935,
      "plate_name": "Agata",
      "official_name": "Agata",
      "provisional_name": false,
      "commune_key": "ALL",
      "commune": "Allada",
      "arrondissement": "Ayou",
      "departement": "Atlantique",
      "name_key": "agata",
      "name_index": 289,
      "digits": 4,
      "blocks": [
        [
          1000,
          1199
        ]
      ],
      "place": {
        "lat": 6.711229,
        "lng": 2.084128
      },
      "frame": [
        2.083221,
        6.709682,
        2.085385,
        6.71191
      ],
      "codes": {
        "total": 19,
        "by_status": {
          "provisional": 19
        }
      },
      "numbers": {
        "lowest": 1000,
        "highest": 1126
      },
      "same_name": [
        "COT-06-001",
        "DAN-01-001"
      ]
    },
    {
      "zone": "COT-06-001",
      "id": 5623,
      "plate_name": "Agata",
      "official_name": "Agata",
      "provisional_name": false,
      "commune_key": "COT",
      "commune": "Cotonou",
      "arrondissement": "6ème Arrondissement",
      "departement": "Littoral",
      "name_key": "agata",
      "name_index": 289,
      "digits": 4,
      "blocks": [
        [
          1200,
          2499
        ]
      ],
      "place": {
        "lat": 6.385043,
        "lng": 2.42272
      },
      "frame": [
        2.417773,
        6.381892,
        2.425396,
        6.387239
      ],
      "codes": {
        "total": 623,
        "by_status": {
          "provisional": 623
        }
      },
      "numbers": {
        "lowest": 1200,
        "highest": 1822
      },
      "same_name": [
        "ALL-06-001",
        "DAN-01-001"
      ]
    },
    … 1 more
  ]
}
```

An unknown area:

```sh
curl -s 'https://addresses.example.bj/v1/areas/COT-99-999'
```

`404 Not Found`

```json
{
  "error": {
    "code": "unknown_area",
    "message": "There is no code area COT-99-999."
  }
}
```

## Issuing (designated issuer only)

These two calls change the register. They need `Authorization: Bearer <key>` with a key from `ISSUE_KEYS`. A deployment without keys is read-only and answers them with `403 read_only`. Only the deployment designated as the issuer for Benin may run with keys (see `server/README.md`). The examples below were run against an issuing test deployment loaded with the real codes of Covè.

### POST /v1/codes

A code for a new compound (`lat`, `lng`, and optionally its `outline` as `[lng, lat]` pairs), or for another door of a compound that has one (`of`: its machine code; the door must be within 80 m). The area is the one of the nearest code within 250 m, else the code area of the point; the number is the free number between the new home's neighbours on the area's Hilbert curve, else the tail reserve, else an extension block of its name. New codes are `provisional` and `on-demand`. The point must be in Benin as `GET /v1/at` decides, including a point in no outline that has a spot code; a point more than 300 m outside the national border never is, whatever outline or spot frame holds it (`engine/SPEC.md` 1b); else `422 outside_country`.

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 7.2167, "lng": 2.3442, "outline": [[2.34414, 7.21665], [2.34426, 7.21665], [2.34426, 7.21675], [2.34414, 7.21675]]}' 'https://addresses.example.bj/v1/codes'
```

`201 Created`

```json
{
  "machine": "BJ-COV-04-001-1110-0",
  "home": "Abayahoué 1110",
  "written": "Abayahoué · 11 10",
  "spoken": "Abayahoué, 11 10",
  "display": "Abayahoué · 11 10",
  "zone": "COV-04-001",
  "number": 1110,
  "check": 0,
  "status": "provisional",
  "issued": "on-demand",
  "issued_at": "2026-10-21T13:45:01Z",
  "entrance": {
    "lat": 7.2167,
    "lng": 2.3442,
    "kind": "centre"
  },
  "spot_code": "COV 07 · 427 FWX",
  "plus_code": "6FV4688V+MMP",
  "official_address": null,
  "official_name": "Abayahoué",
  "area": {
    "zone": "COV-04-001",
    "id": 5708,
    "plate_name": "Abayahoué",
    "official_name": "Abayahoué",
    "provisional_name": false,
    "commune_key": "COV",
    "commune": "Covè",
    "arrondissement": "Houin",
    "departement": "Zou"
  },
  "profile": {
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floor_area_m2": 146.5,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "BJ-COV-04-001-1110-0",
    "home": "Abayahoué 1110",
    "written": "Abayahoué · 11 10",
    "zone": "COV-04-001",
    "official_name": "Abayahoué",
    "number": "1110",
    "check": "0",
    "status": "provisional",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:45:01Z",
    "entrance_lat": "7.2167000",
    "entrance_lng": "2.3442000",
    "entrance_kind": "centre",
    "spot_code": "COV 07 · 427 FWX",
    "official_address": "",
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "146.5",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
}
```

The same building again:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 7.21671, "lng": 2.34421}' 'https://addresses.example.bj/v1/codes'
```

`409 Conflict`

```json
{
  "error": {
    "code": "exists",
    "message": "This building already has its code: Abayahoué · 11 10.",
    "machine": "BJ-COV-04-001-1110-0"
  }
}
```

Another door of a compound:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 7.21705, "lng": 2.34285, "of": "BJ-COV-04-001-1044-3"}' 'https://addresses.example.bj/v1/codes'
```

`201 Created`

```json
{
  "machine": "BJ-COV-04-001-1022-6",
  "home": "Abayahoué 1022",
  "written": "Abayahoué · 10 22",
  "spoken": "Abayahoué, 10 22",
  "display": "Abayahoué · 10 22",
  "zone": "COV-04-001",
  "number": 1022,
  "check": 6,
  "status": "provisional",
  "issued": "on-demand",
  "issued_at": "2026-10-21T13:45:01Z",
  "entrance": {
    "lat": 7.21705,
    "lng": 2.34285,
    "kind": "door"
  },
  "spot_code": "COV 04 · 34F 2WR",
  "plus_code": "6FV4688V+R4H",
  "official_address": null,
  "official_name": "Abayahoué",
  "area": {
    "zone": "COV-04-001",
    "id": 5708,
    "plate_name": "Abayahoué",
    "official_name": "Abayahoué",
    "provisional_name": false,
    "commune_key": "COV",
    "commune": "Covè",
    "arrondissement": "Houin",
    "departement": "Zou"
  },
  "profile": {
    "class": null,
    "use": "residential",
    "kind": "door",
    "structures": 0,
    "floor_area_m2": 0.0,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "BJ-COV-04-001-1022-6",
    "home": "Abayahoué 1022",
    "written": "Abayahoué · 10 22",
    "zone": "COV-04-001",
    "official_name": "Abayahoué",
    "number": "1022",
    "check": "6",
    "status": "provisional",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:45:01Z",
    "entrance_lat": "7.2170500",
    "entrance_lng": "2.3428500",
    "entrance_kind": "door",
    "spot_code": "COV 04 · 34F 2WR",
    "official_address": "",
    "class": "",
    "use": "residential",
    "kind": "door",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
}
```

A door too far from its compound:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 7.2167, "lng": 2.3442, "of": "BJ-COV-04-001-1000-3"}' 'https://addresses.example.bj/v1/codes'
```

`422 Unprocessable Entity`

```json
{
  "error": {
    "code": "too_far",
    "message": "That door is more than 80 m from Abayahoué · 10 00."
  }
}
```

Without a key:

```sh
curl -s -X POST -H 'Content-Type: application/json' -d '{"lat": 7.2167, "lng": 2.3442}' 'https://addresses.example.bj/v1/codes'
```

`401 Unauthorized`

```json
{
  "error": {
    "code": "unauthorized",
    "message": "A valid issuing key is required (Authorization: Bearer <key>)."
  }
}
```

On a read-only deployment:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 7.2167, "lng": 2.3442}' 'https://addresses.example.bj/v1/codes'
```

`403 Forbidden`

```json
{
  "error": {
    "code": "read_only",
    "message": "This deployment does not issue codes: it serves the published registry only."
  }
}
```

### PATCH /v1/codes/{machine}

Sets the status (`provisional`, `confirmed`, `retired`) or moves the entrance to the real gate (at most 80 m, and never more than 300 m outside the national border: `422 outside_country`). A retired code stays retired and its number is never given again. Every change is logged in the `changes` table with the key that made it.

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"status": "confirmed"}' 'https://addresses.example.bj/v1/codes/BJ-COV-04-001-1110-0'
```

`200 OK`

```json
{
  "machine": "BJ-COV-04-001-1110-0",
  "home": "Abayahoué 1110",
  "written": "Abayahoué · 11 10",
  "spoken": "Abayahoué, 11 10",
  "display": "Abayahoué · 11 10",
  "zone": "COV-04-001",
  "number": 1110,
  "check": 0,
  "status": "confirmed",
  "issued": "on-demand",
  "issued_at": "2026-10-21T13:45:01Z",
  "entrance": {
    "lat": 7.2167,
    "lng": 2.3442,
    "kind": "centre"
  },
  "spot_code": "COV 07 · 427 FWX",
  "plus_code": "6FV4688V+MMP",
  "official_address": null,
  "official_name": "Abayahoué",
  "area": {
    "zone": "COV-04-001",
    "id": 5708,
    "plate_name": "Abayahoué",
    "official_name": "Abayahoué",
    "provisional_name": false,
    "commune_key": "COV",
    "commune": "Covè",
    "arrondissement": "Houin",
    "departement": "Zou"
  },
  "profile": {
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floor_area_m2": 146.5,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "BJ-COV-04-001-1110-0",
    "home": "Abayahoué 1110",
    "written": "Abayahoué · 11 10",
    "zone": "COV-04-001",
    "official_name": "Abayahoué",
    "number": "1110",
    "check": "0",
    "status": "confirmed",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:45:01Z",
    "entrance_lat": "7.2167000",
    "entrance_lng": "2.3442000",
    "entrance_kind": "centre",
    "spot_code": "COV 07 · 427 FWX",
    "official_address": "",
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "146.5",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
}
```

Moving the entrance to the gate:

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"entrance": {"lat": 7.21661, "lng": 2.3442}}' 'https://addresses.example.bj/v1/codes/BJ-COV-04-001-1110-0'
```

`200 OK`

```json
{
  "machine": "BJ-COV-04-001-1110-0",
  "home": "Abayahoué 1110",
  "written": "Abayahoué · 11 10",
  "spoken": "Abayahoué, 11 10",
  "display": "Abayahoué · 11 10",
  "zone": "COV-04-001",
  "number": 1110,
  "check": 0,
  "status": "confirmed",
  "issued": "on-demand",
  "issued_at": "2026-10-21T13:45:01Z",
  "entrance": {
    "lat": 7.21661,
    "lng": 2.3442,
    "kind": "gate"
  },
  "spot_code": "COV 07 · 427 FQX",
  "plus_code": "6FV4688V+JMW",
  "official_address": null,
  "official_name": "Abayahoué",
  "area": {
    "zone": "COV-04-001",
    "id": 5708,
    "plate_name": "Abayahoué",
    "official_name": "Abayahoué",
    "provisional_name": false,
    "commune_key": "COV",
    "commune": "Covè",
    "arrondissement": "Houin",
    "departement": "Zou"
  },
  "profile": {
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floor_area_m2": 146.5,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "BJ-COV-04-001-1110-0",
    "home": "Abayahoué 1110",
    "written": "Abayahoué · 11 10",
    "zone": "COV-04-001",
    "official_name": "Abayahoué",
    "number": "1110",
    "check": "0",
    "status": "confirmed",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:45:01Z",
    "entrance_lat": "7.2166100",
    "entrance_lng": "2.3442000",
    "entrance_kind": "gate",
    "spot_code": "COV 07 · 427 FQX",
    "official_address": "",
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "146.5",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
}
```

Retiring it:

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"status": "retired"}' 'https://addresses.example.bj/v1/codes/BJ-COV-04-001-1110-0'
```

`200 OK`

```json
{
  "machine": "BJ-COV-04-001-1110-0",
  "home": "Abayahoué 1110",
  "written": "Abayahoué · 11 10",
  "spoken": "Abayahoué, 11 10",
  "display": "Abayahoué · 11 10",
  "zone": "COV-04-001",
  "number": 1110,
  "check": 0,
  "status": "retired",
  "issued": "on-demand",
  "issued_at": "2026-10-21T13:45:01Z",
  "entrance": {
    "lat": 7.21661,
    "lng": 2.3442,
    "kind": "gate"
  },
  "spot_code": "COV 07 · 427 FQX",
  "plus_code": "6FV4688V+JMW",
  "official_address": null,
  "official_name": "Abayahoué",
  "area": {
    "zone": "COV-04-001",
    "id": 5708,
    "plate_name": "Abayahoué",
    "official_name": "Abayahoué",
    "provisional_name": false,
    "commune_key": "COV",
    "commune": "Covè",
    "arrondissement": "Houin",
    "departement": "Zou"
  },
  "profile": {
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floor_area_m2": 146.5,
    "rule": null,
    "estate": null
  },
  "registry": {
    "machine": "BJ-COV-04-001-1110-0",
    "home": "Abayahoué 1110",
    "written": "Abayahoué · 11 10",
    "zone": "COV-04-001",
    "official_name": "Abayahoué",
    "number": "1110",
    "check": "0",
    "status": "retired",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:45:01Z",
    "entrance_lat": "7.2166100",
    "entrance_lng": "2.3442000",
    "entrance_kind": "gate",
    "spot_code": "COV 07 · 427 FQX",
    "official_address": "",
    "class": "residential",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "146.5",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)"
}
```

A retired code cannot come back:

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"status": "provisional"}' 'https://addresses.example.bj/v1/codes/BJ-COV-04-001-1110-0'
```

`409 Conflict`

```json
{
  "error": {
    "code": "retired",
    "message": "A retired code stays retired: its number is never used again."
  }
}
```

## Errors

Every error has the same shape and an HTTP status that matches it.

An unknown endpoint:

```sh
curl -s 'https://addresses.example.bj/v1/addresses'
```

`404 Not Found`

```json
{
  "error": {
    "code": "no_such_endpoint",
    "message": "There is no endpoint /v1/addresses. See /v1/info and docs/api.md."
  }
}
```

A method an endpoint does not take:

```sh
curl -s -X DELETE 'https://addresses.example.bj/v1/codes/BJ-COT-12-001-1807-4'
```

`405 Method Not Allowed`

```json
{
  "error": {
    "code": "method_not_allowed",
    "message": "DELETE is not allowed here; use GET, PATCH."
  }
}
```

A malformed parameter:

```sh
curl -s 'https://addresses.example.bj/v1/at?lat=north&lng=2.39'
```

`400 Bad Request`

```json
{
  "error": {
    "code": "bad_parameter",
    "message": "lat and lng are decimal degrees (WGS 84)."
  }
}
```
