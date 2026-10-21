#!/usr/bin/env python3
"""Every Beninese footprint's code area (engine/SPEC.md 3.1).

  python3 tools/assign-areas.py <work folder>

Reads <work>/buildings-pts.csv (tools/extract-buildings.py: bid, lon, lat, unit, dens) and
model/keys.json, and applies the engine's area lookup (bj_engine.code_area) from the arrondissement
the extraction found: the nearest named place of the arrondissement (local metres), or area 000
when the arrondissement has no named place. A footprint in no arrondissement polygon (a few on the
coast, the lagoons and the border) takes the nearest named place in the country.
Footprints are streamed; standard library only.

Writes <work>/area-of.csv (bid, aid = the area key "COT-09-004", dens), <work>/area-counts-raw.json
and <work>/area-boxes.json (each area's box of footprint centres: its numbering frame).
"""
import collections, csv, json, math, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402

work = os.path.abspath(sys.argv[1])
W = lambda f: os.path.join(work, f)
K = E.keys()
by_id = K['_arr']
allp = []
for a in K['arrondissements']:
    for p in a['places']:
        allp.append((p['lon'], p['lat'], E.area_key(a['commune'], a['number'], p['index'])))
G = collections.defaultdict(list)
for x, y, k in allp:
    G[(int(x // 0.1), int(y // 0.1))].append((x, y, k))


def nearest_in_country(lon, lat):
    cl = math.cos(math.radians(lat)) ** 2
    for r in range(1, 40):
        cand = [c for dx in range(-r, r + 1) for dy in range(-r, r + 1) for c in G.get((int(lon // 0.1) + dx, int(lat // 0.1) + dy), ())]
        if cand:
            return min(cand, key=lambda c: ((c[0] - lon) ** 2 * cl + (c[1] - lat) ** 2, c[2]))[2]
    raise SystemExit('no place near %s %s' % (lon, lat))


counts, stats = collections.Counter(), collections.Counter()
box = {}
with open(W('buildings-pts.csv'), encoding='utf-8', newline='') as f, open(W('area-of.csv'), 'w', newline='') as o:
    w = csv.writer(o)
    w.writerow(['bid', 'aid', 'dens'])
    for r in csv.DictReader(f):
        lat, lon = float(r['lat']), float(r['lon'])
        a = by_id.get(r['unit'])
        if a is None:
            aid = nearest_in_country(lon, lat)
            stats['noUnit'] += 1
        elif not a['places']:
            aid = E.area_key(a['commune'], a['number'], 0)
        else:
            cl = math.cos(math.radians(lat)) ** 2
            p = min(a['places'], key=lambda p: ((p['lon'] - lon) ** 2 * cl + (p['lat'] - lat) ** 2, p['index']))
            aid = E.area_key(a['commune'], a['number'], p['index'])
        counts[aid] += 1
        b = box.get(aid)
        box[aid] = [lon, lat, lon, lat] if b is None else [min(b[0], lon), min(b[1], lat), max(b[2], lon), max(b[3], lat)]
        w.writerow([r['bid'], aid, r['dens']])
json.dump(dict(sorted(counts.items())), open(W('area-counts-raw.json'), 'w'))
json.dump(dict(sorted(box.items())), open(W('area-boxes.json'), 'w'))
print(sum(counts.values()), 'footprints,', len(counts), 'areas with footprints,', stats['noUnit'], 'with no arrondissement')
