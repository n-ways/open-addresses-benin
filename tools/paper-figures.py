#!/usr/bin/env python3
"""Data of the paper's figures (docs/figures/*.dat), from the published files only.

  python3 tools/paper-figures.py

Reads registry/ (Cotonou's file and the area table), engine/data/register.json,
model/names.json, model/units/communes.geojson and model/stats/building-stats.json,
and writes the small tables the TikZ sources in docs/figures/ plot. Standard library only.

  communes-c<k>.dat   commune outlines (simplified to about 400 m), one file per
                      density class of compounds per square kilometre
  towns.dat           the places named on the map
  area-sizes.dat      areas by compounds (logarithmic bins), four- and five-digit
  cadjehoun.dat       the compounds of Cadjéhoun (Cotonou, 12th arrondissement):
                      position in metres inside the area's frame, and number
  hilbert3.dat        the order-3 Hilbert curve: cell and distance along the curve
  zongo-blocks.dat    the 26 blocks of the name Zongo in its national range
  footprints.dat      footprints by département and source
  spot-cell.dat       the three levels of the spot code of Cadjéhoun 18 07
"""
import csv, difflib, gzip, json, math, os, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, 'docs', 'figures')
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402


def load(*p):
    with open(os.path.join(REPO, *p), encoding='utf-8') as f:
        return json.load(f)


def write(name, header, rows):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
        if header:
            f.write(header + '\n')
        for r in rows:
            f.write(r + '\n')


# ------------------------------------------------------------------ map

def dp(pts, tol):
    """Douglas-Peucker simplification of a polyline (degrees)."""
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1e-12
    best, at = 0.0, 0
    for i in range(1, len(pts) - 1):
        x, y = pts[i]
        d = abs(dy * (x - x0) - dx * (y - y0)) / n
        if d > best:
            best, at = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return dp(pts[:at + 1], tol)[:-1] + dp(pts[at:], tol)


def simplify_ring(ring, tol):
    """A closed ring split at its farthest point from the first, each half simplified."""
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    x0, y0 = ring[0]
    far = max(range(len(ring)), key=lambda i: (ring[i][0] - x0) ** 2 + (ring[i][1] - y0) ** 2)
    out = dp(ring[:far + 1], tol)[:-1] + dp(ring[far:] + [ring[0]], tol)
    return out


def ring_km2(ring):
    lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
    kx, ky = 111.320 * math.cos(lat0), 110.574
    s = 0.0
    for (xa, ya), (xb, yb) in zip(ring, ring[1:] + ring[:1]):
        s += xa * kx * yb * ky - xb * kx * ya * ky
    return abs(s) / 2


def fold(name):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return ''.join(ch for ch in s if ch.isalnum())


BREAKS = (25, 50, 100, 500)   # compounds per km²: classes c1 (< 25) to c5 (>= 500)


def communes():
    keys = {fold(c['name']): c['key'] for c in load('model', 'keys.json')['communes']}
    units = load('model', 'stats', 'building-stats.json')['units']
    gj = load('model', 'units', 'communes.geojson')
    cls = {k: [] for k in range(1, 6)}
    dens, seen = [], set()
    for f in gj['features']:
        nm = fold(f['properties']['name'])
        key = keys.get(nm) or keys[difflib.get_close_matches(nm, keys, 1, 0.7)[0]]
        seen.add(key)
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        km2 = sum(ring_km2([tuple(p) for p in poly[0]]) for poly in polys)
        d = units[key]['compounds'] / km2
        dens.append((d, key))
        k = 1 + sum(d >= b for b in BREAKS)
        for poly in polys:
            ring = simplify_ring([tuple(p) for p in poly[0]], 0.003)
            cls[k].append(ring)
    assert len(seen) == len(keys) == 77, 'every commune matched once'
    for k, rings in cls.items():
        rows = []
        for ring in rings:
            rows += [f'{x:.4f} {y:.4f}' for x, y in ring] + ['nan nan']
        write(f'communes-c{k}.dat', 'lon lat', rows)
    return sorted(dens)


# name, lon, lat, anchor of the label (the points are the compounds of section 5 nearest each town)
TOWNS = [('Cotonou', 2.4183, 6.3654, 'north west'), ('Porto-Novo', 2.6036, 6.4969, 'west'), ('Abomey', 1.9912, 7.1829, 'east'),
         ('Parakou', 2.6303, 9.3372, 'west'), ('Djougou', 1.6661, 9.7085, 'west'), ('Natitingou', 1.3797, 10.3042, 'west'),
         ('Malanville', 3.3859, 11.8623, 'east'), ('Kandi', 2.9386, 11.1342, 'west'), ('Ouidah', 2.0851, 6.3622, 'east')]


# ------------------------------------------------------------ area sizes

def area_sizes(reg):
    edges = [1, 10, 25, 50, 100, 250, 500, 1000, 2500, 4250, 10000, 25000]
    rows = []
    for lo, hi in zip(edges, edges[1:]):
        c4 = sum(1 for a in reg['areas'] if lo <= a['compounds'] < hi and a['digits'] == 4)
        c5 = sum(1 for a in reg['areas'] if lo <= a['compounds'] < hi and a['digits'] == 5)
        rows.append(f'{lo} {hi} {c4} {c5}')
    empty = sum(1 for a in reg['areas'] if a['compounds'] == 0)
    return rows, empty


# -------------------------------------------------------------- Cadjéhoun

def cadjehoun(reg):
    a = next(x for x in reg['areas'] if x['key'] == 'COT-12-001')
    x0, y0, x1, y1 = a['frame']
    lat0 = math.radians((y0 + y1) / 2)
    kx, ky = 111320 * math.cos(lat0), 110574
    rows = []
    with gzip.open(os.path.join(REPO, 'registry', 'COT.csv.gz'), 'rt', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['zone'] == 'COT-12-001':
                lon, lat = float(r['entrance_lng']), float(r['entrance_lat'])
                rows.append(f'{(lon - x0) * kx:.1f} {(lat - y0) * ky:.1f} {r["number"]}')
    return rows, (round((x1 - x0) * kx), round((y1 - y0) * ky))


def hilbert3():
    pts = sorted((E.hilbert_d(3, x, y), x, y) for x in range(8) for y in range(8))
    return [f'{x} {y} {d}' for d, x, y in pts]


def zongo():
    e = next(n for n in load('model', 'names.json')['names'] if n['n'] == 'zongo')
    reg = {a['key']: a for a in load('engine', 'data', 'register.json')['areas']}
    rows = []
    for i, (ak, first, size) in enumerate(e['b']):
        main = (2 * size) // 3
        rows.append(f'{i} {first} {first + main} {first + size} {reg[ak]["compounds"]} {ak}')
    return rows


def footprints():
    reg = load('model', 'stats', 'building-stats.json')['regions']
    names = {'Oueme': 'Ouémé'}
    rows = []
    for d, v in sorted(reg.items(), key=lambda kv: kv[1]['structures']):
        rows.append(f'{names.get(d, d)} {v["fromOpenStreetMap"]} {v["structures"] - v["fromOpenStreetMap"]} {v["compounds"]}')
    return rows


def spot_cell():
    lat, lon = 6.3582212, 2.3911161
    e, n = E.to_utm(lat, lon)
    e0, n0 = 429000, 701000
    ix, iy = int((e - e0) // 3), int((n - n0) // 3)
    rows = []
    for level, size in ((1, 1200), (2, 60), (3, 3)):
        span = size // 3
        cx, cy = ix // span * span * 3, iy // span * span * 3
        dx = (ix // span) % 20
        dy = (iy // span) % 20
        rows.append(f'{level} {size} {cx} {cy} {E.ALPHABET[dy]} {E.ALPHABET[dx]}')
    rows.append(f'0 0 {e - e0:.3f} {n - n0:.3f} - -')
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    reg = load('engine', 'data', 'register.json')
    dens = communes()
    write('towns.dat', 'name lon lat anchor', [f'{n} {x} {y} {a}' for n, x, y, a in TOWNS])
    rows, empty = area_sizes(reg)
    write('area-sizes.dat', 'lo hi four five', rows)
    rows, (w, h) = cadjehoun(reg)
    write('cadjehoun.dat', 'x y number', rows)
    write('hilbert3.dat', 'x y d', hilbert3())
    write('zongo-blocks.dat', 'i first tail end compounds area', zongo())
    write('footprints.dat', 'dep osm ml compounds', footprints())
    write('spot-cell.dat', 'level size e n cy cx', spot_cell())
    print(f'communes: density {dens[0][0]:.1f} ({dens[0][1]}) to {dens[-1][0]:.0f} ({dens[-1][1]}) compounds/km²')
    print(f'areas without compounds: {empty}; Cadjéhoun frame {w} m x {h} m')


if __name__ == '__main__':
    main()
