#!/usr/bin/env python3
"""The frozen register of Benin's code areas, at first issue (engine/SPEC.md 3, 5.1).

  python3 tools/build-register.py <work> [--freeze]

1. Every code area's compound count becomes the real one (<work>/area-counts.json, written by
   tools/issue_registry.py group); tools/name_ranges.py then sizes and places the blocks of every
   name on those counts (SPEC 5.1) and writes model/names.json.
2. Every area's numbering frame is the box of its footprints' centres (<work>/area-boxes.json,
   tools/assign-areas.py), widened by 0.0005 degrees (about 55 m) on every side; an area with no
   footprint today gets its place point widened the same way. Frozen with the blocks.
3. Writes engine/data/register.json (what the engines load: communes, arrondissements with their
   spot-code frames, every area with its key, rank, plate and official names, name index, digits,
   blocks (first and last number), frame and place point; the name table and its aliases), engine/data/units.json (the
   arrondissement outlines) and model/stats/register.json (the counts in the papers).
"""
import collections, datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402
import name_ranges  # noqa: E402

work = os.path.abspath(sys.argv[1])
freeze = '--freeze' in sys.argv
counts = json.load(open(os.path.join(work, 'area-counts.json')))
boxes = json.load(open(os.path.join(work, 'area-boxes.json')))
name_ranges.main(None, real=counts)
E._names = None
N = E.names()
K = E.keys()
PAD = 0.0005

areas = []
for arr in sorted(K['arrondissements'], key=lambda a: (a['commune'], a['number'])):
    places = arr['places'] or [{'index': 0, 'name': arr['name']}]
    for p in sorted(places, key=lambda p: p['index']):
        key = E.area_key(arr['commune'], arr['number'], p['index'])
        e, blocks = E.area_blocks(arr['commune'], arr['number'], p['index'])
        rec = p if arr['places'] else arr
        pt = [p.get('lon'), p.get('lat')]
        if pt[0] is None:
            b = boxes.get(key)
            pt = [round((b[0] + b[2]) / 2, 6), round((b[1] + b[3]) / 2, 6)] if b else None
        b = boxes.get(key) or ([pt[0], pt[1], pt[0], pt[1]] if pt else None)
        frame = [round(b[0] - PAD, 6), round(b[1] - PAD, 6), round(b[2] + PAD, 6), round(b[3] + PAD, 6)] if b else None
        a = {'key': key, 'arr': arr['id'], 'name': E.plate_of_place(arr, p), 'officialName': p['name'],
             'nameId': e['i'], 'nameKey': e['n'], 'digits': e['d'], 'blocks': [[f, f + z - 1] for f, z in blocks],
             'frame': frame, 'point': pt, 'compounds': counts.get(key, 0)}
        if rec.get('needsCouncilChoice'):
            a['provisional'] = True
            a['plateCandidates'] = rec.get('plateCandidates', [])
        areas.append(a)
for i, a in enumerate(areas):
    a['id'] = i + 1
reg = {'about': 'N-Ways Addressing for Benin: the frozen register of code areas (engine/SPEC.md 3, 5). Built by tools/build-register.py.',
       'frozen': freeze, 'builtAt': datetime.date.today().isoformat(),
       'communes': K['communes'],
       'arrondissements': [{k: a[k] for k in ('id', 'commune', 'number', 'name', 'e0', 'n0', 'kx', 'ky')} for a in K['arrondissements']],
       'areas': areas,
       'names': [{'n': e['n'], 'p': e['p'], 'i': e['i'], 'd': e['d']} for e in N['names']],
       'aliases': N['aliases']}
os.makedirs(os.path.join(REPO, 'engine', 'data'), exist_ok=True)
json.dump(reg, open(os.path.join(REPO, 'engine', 'data', 'register.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
units = {}
for f in json.load(open(os.path.join(REPO, 'model', 'units', 'arrondissements.geojson'), encoding='utf-8'))['features']:
    g = f['geometry']
    polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    units[f['properties']['id']] = [[[[round(x, 6), round(y, 6)] for x, y in ring] for ring in poly] for poly in polys]
json.dump(units, open(os.path.join(REPO, 'engine', 'data', 'units.json'), 'w'), separators=(',', ':'))

dig = collections.Counter()
for a in areas:
    dig[a['digits']] += a['compounds']
keyc = collections.Counter(a['nameKey'] for a in areas)
cot = [a for a in areas if a['key'].startswith('COT-')]
stats = {'areas': len(areas), 'areasWithCompounds': sum(1 for a in areas if a['compounds']),
         'compounds': sum(a['compounds'] for a in areas),
         'cotonou': {'areas': len(cot), 'compounds': sum(a['compounds'] for a in cot)},
         'nameKeys': len(keyc), 'sharedNames': sum(1 for v in keyc.values() if v > 1),
         'areasInSharedNames': sum(v for v in keyc.values() if v > 1),
         'compoundsInSharedNames': sum(a['compounds'] for a in areas if keyc[a['nameKey']] > 1),
         'areasByDigits': dict(sorted(collections.Counter(a['digits'] for a in areas).items())),
         'compoundsByDigits': dict(sorted(dig.items())),
         'provisionalNames': sum(1 for a in areas if a.get('provisional')),
         'compoundsWithProvisionalNames': sum(a['compounds'] for a in areas if a.get('provisional')),
         'largestArea': max(({'key': a['key'], 'name': a['name'], 'compounds': a['compounds']} for a in areas), key=lambda x: x['compounds'])}
json.dump(stats, open(os.path.join(REPO, 'model', 'stats', 'register.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(stats, ensure_ascii=False))
