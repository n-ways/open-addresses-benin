#!/usr/bin/env python3
"""Benin's national border for the server and any decoder: engine/data/border.json.

  python3 tools/country-border.py <work folder>

Reads <work>/country.geojson (tools/prepare-inputs.py: the OpenStreetMap admin_level 2
boundary of Benin, relation 192784), simplifies every ring with Douglas-Peucker at 45 m on
the local plane, rounds to 1e-6 degrees, and writes engine/data/border.json with
toleranceM = 50. Before writing, it measures both directions: every vertex of the full
boundary within 50 m of the simplified one, and every simplified segment (sampled every
10 m) within 50 m of the full one; it stops if either fails or if the file would reach 1 MB.
engine/reference/bj_border.py reads the file and keeps the 300 m rule exact against it
(engine/SPEC.md 1b). Standard library only.
"""
import json, math, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_border as B  # noqa: E402

EPS_M = 45.0
TOLERANCE_M = 50.0
OUT = os.path.join(REPO, 'engine', 'data', 'border.json')


def simplify(ring, eps):
    """Douglas-Peucker on a closed ring (first point repeated last), in local metres."""
    lat0 = sum(p[1] for p in ring) / len(ring)
    c = math.cos(math.radians(lat0)) * B.M_LON
    xy = [(p[0] * c, p[1] * B.M_LAT) for p in ring]
    n = len(xy)
    if n <= 4:
        return ring
    # Split the ring at its first point and the vertex farthest from it.
    far = max(range(n), key=lambda i: math.hypot(xy[i][0] - xy[0][0], xy[i][1] - xy[0][1]))
    keep = [False] * n
    keep[0] = keep[far] = keep[n - 1] = True
    stack = [(0, far), (far, n - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = xy[a], xy[b]
        vx, vy = bx - ax, by - ay
        ll = vx * vx + vy * vy
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            px, py = xy[i][0] - ax, xy[i][1] - ay
            t = 0.0 if ll == 0 else min(1.0, max(0.0, (px * vx + py * vy) / ll))
            d = math.hypot(px - t * vx, py - t * vy)
            if d > best:
                best, bi = d, i
        if best > eps:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    out = [ring[i] for i in range(n) if keep[i]]
    return out if len(out) >= 4 else ring


def main(work):
    full = B.Border.load(os.path.join(work, 'country.geojson'))
    with open(os.path.join(work, 'country.geojson'), encoding='utf-8') as fh:
        d = json.load(fh)
    geoms = [f['geometry'] for f in d['features']] if d.get('type') == 'FeatureCollection' else [d.get('geometry', d)]
    polys = []
    for g in geoms:
        for poly in ([g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']):
            polys.append([[[round(x, 6), round(y, 6)] for x, y in simplify([tuple(p) for p in ring], EPS_M)] for ring in poly])
    simp = B.Border([r for poly in polys for r in poly], 0.0)
    worst_full = max(simp.edge_m(y1, x1, within=2 * TOLERANCE_M) for x1, y1, _x2, _y2 in full.segs)
    worst_simp = 0.0
    for x1, y1, x2, y2 in simp.segs:
        n = max(1, int(math.hypot((x2 - x1) * B.M_LON, (y2 - y1) * B.M_LAT) // 10))
        for i in range(n + 1):
            t = i / n
            worst_simp = max(worst_simp, full.edge_m(y1 + t * (y2 - y1), x1 + t * (x2 - x1), within=2 * TOLERANCE_M))
    if max(worst_full, worst_simp) > TOLERANCE_M:
        sys.exit('simplified border strays %.1f m / %.1f m from the full one, over %.0f m' % (worst_full, worst_simp, TOLERANCE_M))
    doc = {'source': 'OpenStreetMap, relation 192784 (boundary=administrative, admin_level=2), ODbL',
           'note': 'Benin national border, simplified (engine/SPEC.md 1b)',
           'toleranceM': TOLERANCE_M, 'borderM': B.BORDER_M,
           'measuredM': {'fullToSimplified': round(worst_full, 1), 'simplifiedToFull': round(worst_simp, 1)},
           'vertices': {'full': len(full.segs), 'simplified': sum(len(r) for p in polys for r in p)},
           'polygons': polys}
    text = json.dumps(doc, separators=(',', ':'))
    if len(text) >= 1 << 20:
        sys.exit('border.json would be %d bytes, over 1 MB' % len(text))
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    print('%d -> %d vertices, %d bytes, strays at most %.1f m / %.1f m' % (
        doc['vertices']['full'], doc['vertices']['simplified'], len(text), worst_full, worst_simp))


if __name__ == '__main__':
    main(os.path.abspath(sys.argv[1]))
