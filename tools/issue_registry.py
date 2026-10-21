#!/usr/bin/env python3
"""The compounds of Benin for issuing their codes (engine/SPEC.md 4, 5).

Reads <work>/buildings.csv (tools/sort-buildings.py, sorted by code area) one area at a time.

  python3 tools/issue_registry.py group <work>     compounds and profiles: <work>/compounds.jsonl.gz,
                                                    <work>/area-counts.json, <work>/group-stats.json
  python3 tools/build-register.py <work> --freeze  plate names, national ranges, blocks, frames
  python3 tools/issue_registry.py number <work> <lotes.jsonl.gz>
                                                    numbers every area's compounds inside its block
                                                    and writes the lotes, commune by commune, for the
                                                    N-Ways issuer, which numbers them again and
                                                    refuses any difference

Border: a compound whose point (the centre of its largest structure) lies more than 300 m outside
the national border (<work>/country.geojson, OpenStreetMap admin_level 2) is dropped and counted as
"abroad" in group-stats.json; tools/extract-buildings.py already keeps only footprints whose centre is
inside it, so the count is 0 on the N-Ways inputs.

Grouping: bj_engine.group_footprints (SPEC 4 step 3: enclosure, annex, hut cluster in the rural
communes of Alibori, Atacora, Borgou and Collines, single). Numbering: bj_engine.assign_numbers over
the area's frozen frame and first block (SPEC 5.2), at the centre of the compound's largest structure.

Each lote line: {"key": the main structure's stable id, "muni": the commune key ("COT"), "zone": the
area key ("COT-09-004"), "areaId": the area's rank in the register, "nameId": its name's national
index, "number", "lat", "lon", "anchor", "anchorKind", "gate", "coverage": "official-street" in
Cotonou where a named street is within 30 m, else "nways", "official": "Rue 12.217, Cotonou" or null,
"estate", "rule", "dens", "label": the area key, "structures": [...]} (largest first). Structure ids:
OpenStreetMap "osm:way/<id>"; a Google/Microsoft footprint "nw:" + the first 12 hex characters
of the SHA-1 of its centre to 1e-6 degrees and its area to 1 m2.
"""
import collections, csv, gzip, hashlib, json, os, re, sys

csv.field_size_limit(1 << 30)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402
import bj_border as B  # noqa: E402

TAGS = ['building', 'amenity', 'shop', 'office', 'religion', 'tourism', 'healthcare', 'man_made', 'government', 'craft',
        'building:levels', 'height', 'name', 'roof:material', 'building:material']
NUM = re.compile(r'-?\d+(?:\.\d+)?')


def structure_id(r):
    if r['src'] == 'osm':
        return 'osm:' + r['oid']
    return 'nw:' + hashlib.sha1(f"{float(r['lat']):.6f},{float(r['lon']):.6f},{round(float(r['area']))}".encode()).hexdigest()[:12]


def ring_of(wkt):
    """The outer ring of a footprint's first polygon, as (lon, lat) pairs, closing point dropped."""
    s = wkt[wkt.index('('):]
    first = s.lstrip('(').split(')')[0]
    nums = [float(x) for x in NUM.findall(first)]
    pts = list(zip(nums[0::2], nums[1::2]))
    return pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts


def areas_of(path):
    cur, rows = None, []
    with open(path, encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            if r['aid'] != cur:
                if rows:
                    yield cur, rows
                cur, rows = r['aid'], []
            rows.append(r)
    if rows:
        yield cur, rows


def height(r):
    try:
        return float(r['height'].replace('m', '').strip()) if r['height'] else None
    except ValueError:
        return None


BTAG = {
    'house': 'residential', 'residential': 'residential', 'detached': 'residential', 'apartments': 'residential',
    'hut': 'residential', 'terrace': 'residential', 'semidetached_house': 'residential', 'dormitory': 'residential',
    'commercial': 'commercial', 'retail': 'commercial', 'kiosk': 'commercial', 'supermarket': 'commercial',
    'office': 'office', 'hotel': 'hospitality', 'school': 'education', 'college': 'education', 'university': 'education',
    'kindergarten': 'education', 'hospital': 'health', 'clinic': 'health', 'church': 'religious', 'mosque': 'religious',
    'chapel': 'religious', 'cathedral': 'religious', 'government': 'government', 'public': 'government', 'civic': 'government',
    'military': 'government', 'industrial': 'industrial', 'warehouse': 'industrial', 'hangar': 'industrial',
    'factory': 'industrial', 'garage': 'transport', 'garages': 'transport', 'train_station': 'transport',
    'farm': 'agricultural', 'barn': 'agricultural', 'construction': 'under_construction', 'ruins': 'ruin',
    'shed': 'annex', 'roof': 'annex',
}
CATS = {'shop': 'commercial', 'supermarket': 'commercial', 'market': 'commercial', 'pharmacy': 'health', 'bank': 'commercial',
        'phones': 'commercial', 'salon': 'commercial', 'mechanic': 'commercial', 'food': 'commercial', 'bar': 'commercial',
        'cafe': 'commercial', 'fastfood': 'commercial', 'petrol': 'commercial', 'hotel': 'hospitality', 'school': 'education',
        'hospital': 'health', 'church': 'religious', 'mosque': 'religious', 'police': 'government', 'office': 'office',
        'motorpark': 'transport'}


def profile(r):
    """Use class, confidence, source and floors of one footprint (SPEC 6). Floors come from
    OpenStreetMap only: the Google/Microsoft height is a rendering filler and gives none."""
    b = (r['building'] or '').lower()
    ev = []
    if b and b != 'yes' and b in BTAG:
        ev.append((BTAG[b], 0.85, 'osm:building'))
    if r['amenity'] or r['shop'] or r['office'] or r['government'] or r['tourism'] or r['healthcare']:
        tag = ('health' if r['amenity'] in ('hospital', 'clinic', 'doctors', 'pharmacy') or r['healthcare'] else
               'education' if r['amenity'] in ('school', 'kindergarten', 'college', 'university') else
               'religious' if r['amenity'] == 'place_of_worship' else
               'government' if r['government'] or r['amenity'] in ('townhall', 'courthouse', 'police', 'post_office') else
               'hospitality' if r['tourism'] in ('hotel', 'guest_house', 'hostel', 'motel') else
               'office' if r['office'] else 'commercial')
        ev.append((tag, 0.75, 'osm:tag'))
    if r['poi']:
        cs = [CATS.get(c, 'commercial') for c in r['poi'].split('|')]
        ev.append((max(sorted(set(cs)), key=cs.count), 0.65, 'nways:places-inside'))
    a = float(r['area'])
    if not ev:
        ev.append(('annex', 0.4, 'size') if a < 6 else ('industrial', 0.3, 'size') if a > 2500 else ('residential', 0.45, 'default'))
    ev.sort(key=lambda e: -e[1])
    cls, conf, src = ev[0]
    if cls == 'residential' and any(e[0] in ('commercial', 'office') for e in ev):
        cls, conf, src = 'mixed', 0.6, 'agreement'
    conf = min(0.95, conf + 0.05 * sum(1 for e in ev[1:] if e[0] == cls))
    floors, fsrc = None, None
    try:
        if r['building:levels']:
            floors, fsrc = max(1, int(round(float(r['building:levels'])))), 'osm:building:levels'
    except ValueError:
        pass
    if floors is None and r['src'] == 'osm' and height(r):
        floors, fsrc = E.floors_from_height(height(r)), 'osm:height'
    return {'useClass': cls, 'useConfidence': round(conf, 2), 'useSource': src, 'floors': floors, 'floorsSource': fsrc}


def cmd_group(work):
    # The border decides (SPEC 1b): a compound whose point lies more than 300 m outside the
    # national border of <work>/country.geojson (the full OpenStreetMap boundary) is in a
    # neighbouring country and gets no code, whatever its arrondissement outline says.
    border = B.Border.load(os.path.join(work, 'country.geojson'))
    counts, stats, seen = {}, collections.Counter(), set()
    with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'wt', encoding='utf-8') as out:
        for aid, rows in areas_of(os.path.join(work, 'buildings.csv')):
            fs = []
            for r in rows:
                ring = ring_of(r['wkt'])
                fs.append({'id': structure_id(r), 'ring': ring + ring[:1], 'area': float(r['area']), 'eid': r['eid'] or None,
                           'lat': float(r['lat']), 'lon': float(r['lon']), 'row': r})
            n = 0
            params = E.grouping_params(aid[:3])
            for ms, rule in E.group_footprints(fs, params):
                sts = []
                for i in ms:
                    f, r = fs[i], fs[i]['row']
                    p = profile(r)
                    sts.append({'id': f['id'], 'src': r['src'], 'lat': round(f['lat'], 7), 'lon': round(f['lon'], 7),
                                'areaM2': round(f['area'], 1), 'perimeterM': round(float(r['perim'] or 0), 1),
                                'tags': {t: r[t] for t in TAGS if r.get(t)}, 'places': [x for x in (r['poi'] or '').split('|') if x],
                                'class': p['useClass'], 'confidence': p['useConfidence'], 'classSource': p['useSource'],
                                'floors': p['floors'], 'floorsSource': p['floorsSource'], 'wkt': r['wkt']})
                key = sts[0]['id']
                if border.beyond(fs[ms[0]]['lat'], fs[ms[0]]['lon'], B.BORDER_M):
                    stats['abroad'] += 1
                    continue
                if key in seen:
                    stats['duplicateKey'] += 1
                    continue
                seen.add(key)
                main = fs[ms[0]]['row']
                streets = collections.Counter(fs[k]['row']['street'] for k in ms if fs[k]['row']['street'])
                street = min(streets, key=lambda x: (-streets[x], x)) if streets else None
                rec = {'key': key, 'aid': aid, 'lat': round(fs[ms[0]]['lat'], 7), 'lon': round(fs[ms[0]]['lon'], 7), 'rule': rule,
                       'enclosed': rule == 'enclosure', 'estate': main['estate'] or None, 'dens': int(main['dens'] or 0),
                       'label': aid, 'official': f'{street}, Cotonou' if street else None, 'structures': sts}
                out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                n += 1
                stats['rule:' + rule] += 1
                stats['structures'] += len(sts)
                stats[f'size:{min(len(sts), 7)}'] += 1
            counts[aid] = n
            stats['compounds'] += n
    json.dump(counts, open(os.path.join(work, 'area-counts.json'), 'w'))
    json.dump(dict(stats), open(os.path.join(work, 'group-stats.json'), 'w'), indent=1)
    print(json.dumps(dict(stats)))


def cmd_number(work, out_path):
    """Numbers inside each area's first block, over its frozen frame (engine/data/register.json)."""
    reg = json.load(open(os.path.join(REPO, 'engine', 'data', 'register.json'), encoding='utf-8'))
    areas = {a['key']: a for a in reg['areas']}
    counts = collections.Counter()
    by_area = collections.defaultdict(list)
    with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'rt', encoding='utf-8') as f:
        for line in f:
            c = json.loads(line)
            by_area[c['aid']].append(c)
    with gzip.open(out_path, 'wt', encoding='utf-8') as out:
        for aid in sorted(by_area, key=lambda k: (k[:3], areas[k]['id'])):
            a = areas[aid]
            cs = sorted(by_area.pop(aid), key=lambda c: c['key'])
            first, last = a['blocks'][0]
            size = last - first + 1
            nums = E.assign_numbers([(c['key'], c['lon'], c['lat']) for c in cs], tuple(a['frame']), (first, size))
            for c in sorted(cs, key=lambda c: nums[c['key']]):
                rec = {'key': c['key'], 'muni': aid[:3], 'zone': aid, 'areaId': a['id'], 'nameId': a['nameId'],
                       'number': nums[c['key']], 'lat': c['lat'], 'lon': c['lon'], 'anchor': [c['lat'], c['lon']], 'anchorKind': 'centre',
                       'gate': None, 'coverage': 'official-street' if c['official'] else 'nways', 'official': c['official'],
                       'enclosed': c['enclosed'], 'estate': c['estate'], 'rule': c['rule'], 'dens': c['dens'], 'label': aid,
                       'structures': c['structures']}
                out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                counts['compounds'] += 1
                counts[f'digits:{len(str(rec["number"]))}'] += 1
                counts['officialStreet'] += bool(c['official'])
    print(json.dumps(counts))


if __name__ == '__main__':
    if sys.argv[1] == 'group':
        cmd_group(os.path.abspath(sys.argv[2]))
    elif sys.argv[1] == 'number':
        cmd_number(os.path.abspath(sys.argv[2]), sys.argv[3])
