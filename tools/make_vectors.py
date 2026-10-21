#!/usr/bin/env python3
"""Write engine/reference/test_vectors.json from real Benin points (standard library only).

The points are real buildings from the N-Ways building map (Cotonou capital
extract of 2026-10-18: OpenStreetMap + Google/Microsoft footprints), real
places from OpenStreetMap, and a real 500 m x 380 m block of central Cotonou
(engine/reference/testdata). Re-run after any engine change and review the diff:
a changed vector means a changed code, which the stability rules forbid.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402

POINTS = [
    ('Cotonou, Zogbo (OSM place)', 6.392518, 2.394291),
    ('Cotonou, building with a mapped enclosure near Gbégamey (ML footprint 233.7 m², h 6.1 m)', 6.385013, 2.420889),
    ('Cotonou, school footprint (ML 316.7 m², places: school)', 6.3725247, 2.4620978),
    ('Cotonou, supermarket footprint (OSM 359.2 m²)', 6.3664021, 2.428563),
    ('Cotonou, hospital footprint (OSM building=hospital, 637.2 m²)', 6.3707444, 2.4474113),
    ('Cotonou, Dantokpa (OSM place)', 6.375532, 2.431404),
    ('Cotonou, Agla (OSM place)', 6.375472, 2.369229),
    ('Sô-Ava, Ganvié stilt house (ML footprint centroid)', 6.468357, 2.389748),
    ('Sô-Ava, Ganvié 1 stilt house (ML footprint centroid)', 6.4686, 2.386362),
    ('Parakou, building (ML footprint centroid)', 9.350074, 2.616873),
    ('Natitingou, building (ML footprint centroid)', 10.300156, 1.383612),
    ('Porto-Novo (OSM place)', 6.499072, 2.625336),
    ('Ouidah (OSM place)', 6.366615, 2.08536),
    ('Malanville (OSM place)', 11.866, 3.389),
]


PLATE_AREAS = [('DJO', 8, 15), ('ZAG', 6, 2), ('DJO', 12, 20), ('COM', 5, 40), ('KAR', 4, 17), ('BAN', 5, 22),
               ('COT', 9, 4), ('COT', 1, 9), ('COT', 4, 1), ('COT', 12, 6)]
ALIAS_AREAS = [('DJO', 8, 15), ('ZAG', 6, 2), ('KAR', 4, 17), ('DJO', 12, 20), ('COM', 5, 40)]
COLLIDE_PAIRS = [(('ZAG', 6, 2), ('ZOG', 3, 5)), (('AKP', 4, 15), ('ZEE', 6, 6))]


def _area(k):
    arr = E.keys()['_byCode'][(k[0], k[1])]
    place = next((p for p in arr['places'] if p['index'] == k[2]), None) or {'index': 0, 'name': arr['name']}
    rec = place if arr['places'] else arr
    return arr, place, rec


def plate_row(k):
    arr, place, rec = _area(k)
    out = {'area': list(k), 'official': place['name'], 'plate': E.plate_of_place(arr, place),
           'rule': rec.get('plateRule', 'as-is'), 'needsCouncilChoice': bool(rec.get('needsCouncilChoice'))}
    if rec.get('needsCouncilChoice'):
        out['candidates'] = rec.get('plateCandidates', [])
    return out


def _first(k):
    _, blocks = E.area_blocks(*k)
    return blocks[0][0] + 1


def alias_row(k):
    arr, place, _ = _area(k)
    n = _first(k)
    plate = E.plate_of_place(arr, place)
    d = E.decode_remembered(f"{plate} · {E.spoken_number(n)}")
    return {'official': f"{place['name']} · {E.spoken_number(n)}", 'plate': f"{plate} · {E.spoken_number(n)}",
            'machine': d['machine']}


def collide_row(k):
    arr, place, _ = _area(k)
    n = _first(k)
    text = f"{E.plate_of_place(arr, place)} · {E.spoken_number(n)}"
    d = E.decode_remembered(text)
    return {'text': text, 'official': place['name'], 'commune': d['commune'], 'communeName': d['communeName'],
            'arrondissement': d['arrondissement'], 'quartier': d['quartier'], 'machine': d['machine']}


def same_name_texts(names):
    """Two areas of each shared name, each at the 17th number of its block."""
    out = []
    for name in names:
        e = E.names()['_byName'][E.norm_name(name)]
        for ak, first, size in e['b'][:2]:
            out.append(f"{e['p']} · {E.spoken_number(first + 16)}")
    return out


def not_issued(names):
    """Numbers in a name's spare space, and a number with the wrong digit count."""
    out = []
    for name in names:
        e = E.names()['_byName'][E.norm_name(name)]
        top = max(f + z for _, f, z in e['b'])
        out.append(f"{e['p']} · {E.spoken_number(top)}")
    e = E.names()['_byName'][E.norm_name(names[0])]
    out.append(f"{e['p']} · {E.spoken_number(4817 if e['d'] == 5 else 48170)}")
    return out


def provisional_long():
    """Areas whose provisional plate name is still over the limit."""
    out = []
    for arr in E.keys()['arrondissements']:
        for p in arr['places'] or [arr]:
            if p.get('needsCouncilChoice') and not E.plate_ok(E.plate_of_place(arr, p)):
                k = (arr['commune'], arr['number'], p.get('index', 0) if arr['places'] else 0)
                out.append((E.plate_of_place(arr, p), k))
    return out[:2]


def main():
    spots = []
    for label, lat, lon in POINTS:
        s = E.spot_encode(lat, lon)
        a = E.code_area(lat, lon)
        e, n = E.to_utm(lat, lon)
        spots.append({'label': label, 'lat': lat, 'lon': lon, 'utm31n': [round(e, 3), round(n, 3)],
                      'spot': s['machine'], 'spotDisplay': s['display'], 'decoded': [round(v, 7) for v in E.spot_decode(s['machine'])],
                      'area': {k: a[k] for k in ('commune', 'arrondissement', 'arrondissementName', 'quartier', 'quartierName')}})
    comps, nums = E.demo()
    sample = []
    order = sorted(nums.items(), key=lambda kv: (kv[1][0]['quartierName'], kv[1][1]))
    seen = set()
    for i, (a, c) in order:
        if len(sample) >= 12:
            break
        cp = comps[i]
        if len(cp['structures']) == 1 and len(sample) % 3:
            continue
        sample.append({'centroid': cp['centroid'], 'structures': len(cp['structures']), 'rule': cp['rule'],
                       'class': cp['class'], 'area': [a['commune'], a['arrondissement'], a['quartier'], a['quartierName']],
                       'number': c, 'machine': E.machine(a['commune'], a['arrondissement'], a['quartier'], c),
                       'remembered': E.remembered(a['plateName'], c), 'spokenFr': E.say_fr(c)})
    # provisional number for a new compound in the busiest area of the sample
    from collections import Counter
    busiest = Counter((a['commune'], a['arrondissement'], a['quartier']) for a, _ in nums.values()).most_common(1)[0][0]
    members = {num: tuple(comps[i]['centroid']) for i, (a, num) in nums.items()
               if (a['commune'], a['arrondissement'], a['quartier']) == busiest}
    xs = [v[0] for v in members.values()]
    ys = [v[1] for v in members.values()]
    box = (min(xs), min(ys), max(xs), max(ys))
    newp = (box[0] + (box[2] - box[0]) * 0.37, box[1] + (box[3] - box[1]) * 0.61)
    block = E.area_blocks(*busiest)[1][0]
    prov = E.provisional_number(members, box, *newp, block=block)
    areas = len({(a['commune'], a['arrondissement'], a['quartier']) for a, _ in nums.values()})
    out = {
        'engine': 'bj_engine.py 1.0', 'built': '2026-10-20',
        'damm': [{'digits': d, 'check': E.damm(d)} for d in ('120314817', '090044817', '13', '572', '000000000')],
        'spot': spots,
        'compoundSample': {
            'source': 'engine/reference/testdata/cotonou-sample-*.geojson (OSM + ML footprints, OSM barriers), box ' + str(list(box)),
            'structures': sum(len(c['structures']) for c in comps), 'compounds': len(comps), 'codeAreas': areas,
            'sample': sample,
            'provisional': {'area': list(busiest), 'areaBox': list(box), 'membersInArea': len(members),
                            'block': list(block), 'lon': newp[0], 'lat': newp[1], 'number': prov},
        },
        'machine': [{'parts': list(p), 'code': E.machine(*p)}
                    for p in ((*k, _first(k) + 16) for k in (('COT', 9, 4), ('CAL', 2, 11), ('COT', 5, 5)))],
        'remembered': [{'text': 'Zogbo · 48 17', 'parsed': ['Zogbo', 4817, None]},
                       {'text': 'Zogbo 4817', 'parsed': ['Zogbo', 4817, None]},
                       {'text': 'Zongo · 15 170', 'parsed': ['Zongo', 15170, None]},
                       {'text': 'Ganvié 1 · 12 03, Abomey-Calavi', 'parsed': ['Ganvié 1', 1203, 'Abomey-Calavi']}],
        'spokenFr': [{'number': n, 'fr': E.say_fr(n)} for n in (4817, 1203, 7091, 8080, 9971, 15170, 19300, 10070, 21105)],
        'normalised': [{'name': n, 'key': E.norm_name(n)} for n in
                       ('Zogbo', 'Gbèdji', 'Gbedji', 'Gbédji', 'Ganvié I', 'Ganvié 1', 'Ganvie 1er', 'Ouèssè', 'Wèssè',
                        'Tchetti', 'Ceti', 'Ouémè Hounli', 'Ouèmèhounli', 'Fifadji', 'La Haie Vive', 'Haie-Vive', 'Dassa')],
        # Same name, different places: the remembered form alone decodes to one area each.
        'sameName': [dict(text=t, **{k: v for k, v in E.decode_remembered(t).items() if k != 'number'})
                     for t in same_name_texts(('Zongo', 'Agata', 'Gbèdji', 'Ganvié 1'))],
        'notIssued': not_issued(('Zongo', 'Agata', 'Zogbo')),
        # Plate names: at most 12 characters and 2 words.
        'plateNames': [plate_row(k) for k in PLATE_AREAS],
        # The official name typed in full still decodes, to the same compound as the plate name.
        'officialAlias': [alias_row(k) for k in ALIAS_AREAS],
        # Names that only collide after shortening share one range and decode to different places.
        'collideAfterShortening': [[collide_row(k) for k in pair] for pair in COLLIDE_PAIRS],
        # A plate name still over the limit (flagged): issued under it provisionally; the commune may choose once.
        'plateRefused': [f"{n} · {E.spoken_number(_first(k) - 1)}" for n, k in provisional_long()],
        'plateLength': [{'name': n, 'length': E._P.plate_length(n), 'words': E._P.word_count(n, E.PLATE_LANG),
                         'ok': E.plate_ok(n)} for n in
                        ('Zogbo', 'Ganvié 1', 'Haie-Vive', 'Dar Es Salam', 'St Prosper', 'Soukoumpérou', 'Tchanhounkpamè',
                         'Lém-Ferreira', 'Camp Peulh Tovari', 'Peulh Tovari')],
    }
    p = os.path.join(REPO, 'engine', 'reference', 'test_vectors.json')
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('wrote', p)


if __name__ == '__main__':
    main()
