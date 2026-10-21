#!/usr/bin/env python3
"""Conformance vectors for every port of the engine: engine/reference/vectors.json.

Computed by the reference engine (engine/reference/bj_engine.py) on the frozen register
(model/keys.json, model/names.json, engine/data/register.json); every other implementation
of the engine (the N-Ways issuer's among them) must reproduce them value for value.

  python3 tools/vectors.py
"""
import csv, gzip, json, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402


def decode(text):
    try:
        if text.upper().startswith('BJ-'):
            p = E.parse_machine(text)
            return {'text': text, 'machine': E.machine(p['commune'], p['arrondissement'], p['quartier'], p['number'])}
        return {'text': text, 'machine': E.decode_remembered(text)['machine']}
    except ValueError as e:
        return {'text': text, 'error': str(e)}


def spot_case(lat, lon):
    """A point in no outline (SPEC 2.4): its grid arrondissement and spot code, or the refusal."""
    if E.arrondissement_at(lat, lon) is not None:
        return None
    a = E.spot_arrondissement(lat, lon)
    if a is None:
        try:
            E.spot_encode(lat, lon)
        except ValueError as e:
            return {'lat': lat, 'lon': lon, 'error': str(e)}
        raise AssertionError('a refused point must not encode')
    s = E.spot_encode(lat, lon)
    e, n = E.to_utm(lat, lon)
    ix, iy = E._cells(e, n, a)
    clamped = max(E._beyond(ix, a['kx']), E._beyond(iy, a['ky'])) > 0
    return {'lat': lat, 'lon': lon, 'arrondissement': '%s-%02d' % (a['commune'], a['number']), 'clamped': clamped,
            'machine': s['machine'], 'display': s['display'], 'decoded': list(E.spot_decode(s['machine']))}


def spots_outside(rnd):
    """Spot codes of points in no outline: issued compounds of Karimama, Athiémé and Ouaké whose
    entrance lies in no outline (every one beyond a frame, and a sample of the others), then random
    points along the outlines, in slivers, beyond the frames (the frame's nearest cell) and refused
    (more than 10 km from every outline, or 999 m beyond every frame)."""
    out, rest = [], []
    for com in ('ATH', 'KAR', 'OUA'):
        with gzip.open(os.path.join(REPO, 'registry', com + '.csv.gz'), 'rt', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                lat, lon = float(r['entrance_lat']), float(r['entrance_lng'])
                c = spot_case(lat, lon)
                if c:
                    c['issued'] = r['machine']
                    (out if c['clamped'] else rest).append(c)
    out += rnd.sample(rest, min(300, len(rest)))
    want = {'nearest': 200, 'clamped': 60, 'refused': 60}
    got = dict.fromkeys(want, 0)
    polys = E.polygons()
    for _ in range(500000):
        if got == want:
            break
        u = rnd.random()
        if u < 0.4:     # anywhere around Benin
            lat, lon = rnd.uniform(5.9, 12.7), rnd.uniform(0.5, 4.0)
        elif u < 0.8:   # near an outline vertex
            _aid, ps, _box = rnd.choice(polys)
            ring = rnd.choice(ps)[0]
            x, y = rnd.choice(ring)
            lat, lon = y + rnd.uniform(-0.05, 0.05), x + rnd.uniform(-0.05, 0.05)
        else:           # just beyond a frame edge
            a = rnd.choice(E.keys()['arrondissements'])
            w, h = 20 ** a['kx'] * E.CELL_M, 20 ** a['ky'] * E.CELL_M
            e = a['e0'] + rnd.uniform(-1500, 0) if rnd.random() < 0.5 else a['e0'] + w + rnd.uniform(0, 1500)
            n = a['n0'] + rnd.uniform(0, h)
            if rnd.random() < 0.5:
                e = a['e0'] + rnd.uniform(0, w)
                n = a['n0'] + rnd.uniform(-1500, 0) if rnd.random() < 0.5 else a['n0'] + h + rnd.uniform(0, 1500)
            lat, lon = E.from_utm(e, n)
        c = spot_case(lat, lon)
        if c is None:
            continue
        kind = 'refused' if 'error' in c else 'clamped' if c['clamped'] else 'nearest'
        if got[kind] < want[kind]:
            got[kind] += 1
            out.append(c)
    return out


def main():
    rnd = random.Random(247)
    reg = json.load(open(os.path.join(REPO, 'engine', 'data', 'register.json'), encoding='utf-8'))
    areas = reg['areas']
    words = sorted({a['name'] for a in areas} | {a['officialName'] for a in areas})
    tricky = ['Gbèdji', 'Gbedji', 'Gbédji', 'Ganvié I', 'Ganvié 1', 'Ganvie 1er', 'Ouèssè', 'Wèssè', 'Tchetti', 'Ceti',
              'Ouémè Hounli', 'Ouèmèhounli', 'La Haie Vive', 'Haie-Vive', 'St Michel', 'Saint-Michel', 'Ɖokpa', 'Dokpa',
              'Zogbo', 'ZOGBO', 'Les Cocotiers', 'Akpakpa 2ème', 'Akpakpa II']
    keys = [[w, E.norm_name(w)] for w in tricky + rnd.sample(words, 700)]
    forms, found = [], []
    for a in rnd.sample(areas, 500):
        com, an, q = a['key'].split('-')
        lo, hi = a['blocks'][0]
        n = rnd.randint(lo, hi)
        forms.append({'zone': a['key'], 'number': n, 'check': E.check_digit(a['nameId'], n), 'home': '%s %d' % (a['name'], n),
                      'written': '%s · %s' % (a['name'], E.spoken_number(n)),
                      'machine': E.machine(com, int(an), int(q), n)})
        for text in ('%s %d' % (a['name'], n), '%s · %s' % (a['name'], E.spoken_number(n)), E.machine(com, int(an), int(q), n),
                     '%s %d, %s' % (a['name'], n, next(c['name'] for c in reg['communes'] if c['key'] == com))):
            found.append(decode(text))
    off = [a for a in areas if E.norm_name(a['officialName']) != E.norm_name(a['name']) and E.norm_name(a['officialName']) in reg['aliases']]
    for a in rnd.sample(off, min(150, len(off))):
        found.append(decode('%s %d' % (a['officialName'], a['blocks'][0][0] + 1)))
    for a in rnd.sample(areas, 80):
        com, an, q = a['key'].split('-')
        n = a['blocks'][0][0] + 3
        found.append(decode('BJ-%s-%s-%s-%d-%d' % (com, an, q, n, (E.check_digit(a['nameId'], n) + 1) % 10)))
        found.append(decode('%s %d, Nulle Part' % (a['name'], n)))
        found.append(decode('%s %d' % (a['name'], a['blocks'][-1][1] + 1)))
    found += [decode(t) for t in ('Nulle Part 1234', 'Zogbo 481', 'Zongo 1 51 70')]
    spots = []
    while len(spots) < 500:
        lat, lon = rnd.uniform(6.2, 12.4), rnd.uniform(0.8, 3.8)
        ca = E.code_area(lat, lon)
        if ca is None:
            continue
        s = E.spot_encode(lat, lon)
        dl, dn = E.spot_decode(s['machine'])
        spots.append({'lat': lat, 'lon': lon, 'area': E.area_key(ca['commune'], ca['arrondissement'], ca['quartier']),
                      'machine': s['machine'], 'display': s['display'], 'decoded': [dl, dn]})
    for _ in range(150):    # Cotonou and Abomey-Calavi, densely
        lat, lon = rnd.uniform(6.34, 6.50), rnd.uniform(2.30, 2.47)
        ca = E.code_area(lat, lon)
        if ca is None:
            continue
        s = E.spot_encode(lat, lon)
        dl, dn = E.spot_decode(s['display'])
        spots.append({'lat': lat, 'lon': lon, 'area': E.area_key(ca['commune'], ca['arrondissement'], ca['quartier']),
                      'machine': s['machine'], 'display': s['display'], 'decoded': [dl, dn]})
    big = max(areas, key=lambda a: a['blocks'][0][1] - a['blocks'][0][0])
    x0, y0, x1, y1 = big['frame']
    first, last = big['blocks'][0]
    block = (first, last - first + 1)
    comps = [{'id': 'c%02d' % k, 'lat': y0 + rnd.uniform(0, y1 - y0), 'lon': x0 + rnd.uniform(0, x1 - x0)} for k in range(41)]
    nums = E.assign_numbers([(c['id'], c['lon'], c['lat']) for c in comps], tuple(big['frame']), block)
    existing = {nums[c['id']]: (c['lon'], c['lat']) for c in comps}
    inserts = []
    for _ in range(60):
        lat, lon = y0 + rnd.uniform(0, y1 - y0), x0 + rnd.uniform(0, x1 - x0)
        n = E.provisional_number(existing, tuple(big['frame']), lon, lat, block)
        inserts.append({'lat': lat, 'lon': lon, 'number': n})
        existing[n] = (lon, lat)
    hil = [[x, y, E.hilbert_d(16, x, y)] for x, y in ((0, 0), (1, 0), (65535, 65535), (12345, 54321), (40000, 2))]
    utm = []
    for _ in range(60):
        lat, lon = rnd.uniform(6.2, 12.4), rnd.uniform(0.8, 3.8)
        e, n = E.to_utm(lat, lon)
        utm.append([lat, lon, e, n])
    outside = spots_outside(rnd)
    out = {'note': 'Computed by engine/reference/bj_engine.py on the frozen register; every port must match.',
           'nameKeys': keys, 'forms': forms, 'found': found, 'spots': spots, 'spotsOutside': outside,
           'numbering': {'zone': big['key'], 'compounds': comps, 'numbers': nums, 'inserts': inserts},
           'hilbert': hil, 'utm': utm, 'spoken': [[n, E.spoken_number(n)] for n in (1000, 4817, 15170, 10000, 99999)]}
    json.dump(out, open(os.path.join(REPO, 'engine', 'reference', 'vectors.json'), 'w'), ensure_ascii=False, indent=0)
    print(len(keys), 'name keys,', len(forms), 'forms,', len(found), 'decodings,', len(spots), 'spots,', len(outside), 'spots outside every outline,',
          len(inserts), 'inserts')


if __name__ == '__main__':
    main()
