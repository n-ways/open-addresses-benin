#!/usr/bin/env python3
"""National name ranges for Benin: "Zogbo · 46 17" is unique in the whole country on
its own, without the commune, because one area in four shares its name with another.

Every code area (quartier / village of model/keys.json) is counted, its PLATE
name (the short remembered name, at most 12 characters and 2 words, written into
keys.json by tools/build_keys.py) is normalised (engine: bj_engine.norm_name),
and all areas that share a normalised plate name draw their numbers from ONE
national range for that name, cut into frozen blocks (one per area) with spare
room left for future areas of the same name. The official name of an area is an
alias of its plate name when it maps to one plate name only.

Inputs:
  model/keys.json, model/units/arrondissements.geojson
  a 1-in-10 sample of building centroids (x,y CSV; the same sample as
  tools/national-areas.py, 521,280 points from the N-Ways building map)

Outputs:
  model/names.json             name table: index, digits, blocks (frozen at issue)
  model/stats/name-ranges.json counts for the papers

  python3 tools/name_ranges.py <sample.csv> [counts-cache.json]

The optional cache keeps the per-area building counts of the sample (the only
slow step), so the table can be rebuilt after a naming change without the
point-in-polygon pass.
"""
import collections
import csv
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402

SAMPLE_FACTOR = 10          # the sample is 1 building in 10
RATIO = 0.813               # compounds per structure (Cotonou, model/stats/capital-stats.json)


def count_sample(sample_path):
    K = E.keys()
    polys = {aid: (ps, bb) for aid, ps, bb in E.polygons()}
    # grid index of arrondissement outlines, 0.05 degree cells
    G = collections.defaultdict(list)
    C = 0.05
    for aid, (ps, (x0, y0, x1, y1)) in polys.items():
        for gx in range(int(x0 // C), int(x1 // C) + 1):
            for gy in range(int(y0 // C), int(y1 // C) + 1):
                G[(gx, gy)].append(aid)
    byid = K['_arr']
    count = collections.Counter()
    outside = 0
    with open(sample_path) as fh:
        for r in csv.DictReader(fh):
            x, y = float(r['x']), float(r['y'])
            arr = None
            for aid in G.get((int(x // C), int(y // C)), ()):
                ps, (x0, y0, x1, y1) = polys[aid]
                if x0 <= x <= x1 and y0 <= y <= y1 and any(E._in_polygon(x, y, p) for p in ps):
                    arr = byid.get(aid)
                    break
            if arr is None:
                outside += 1
                continue
            best = None
            cl = math.cos(math.radians(y)) ** 2
            for p in arr['places']:
                d = (p['lon'] - x) ** 2 * cl + (p['lat'] - y) ** 2
                if best is None or d < best[0]:
                    best = (d, p['index'])
            count[(arr['commune'], arr['number'], best[1] if best else 0)] += 1
    return count, outside


def main(sample_path, cache=None, real=None):
    """real: {area key "COT-09-004": compounds} at first issue (tools/build-register.py); the
    blocks are then sized on the compounds actually grouped, not on the sample's estimate."""
    K = E.keys()
    arrs = K['arrondissements']
    if real is not None:
        count, outside = None, 0
    elif cache and os.path.exists(cache):
        with open(cache) as fh:
            c = json.load(fh)
        count = collections.Counter()
        for k, v in c['count'].items():
            com, an, q = k.split('|')
            count[(com, int(an), int(q))] = v
        outside = c['outside']
    else:
        count, outside = count_sample(sample_path)
        if cache:
            with open(cache, 'w') as fh:
                json.dump({'count': {f'{k[0]}|{k[1]}|{k[2]}': v for k, v in count.items()}, 'outside': outside}, fh)

    areas = []
    for a in arrs:
        places = a['places'] or [{'index': 0, 'name': a['name']}]
        for p in places:
            k = (a['commune'], a['number'], p['index'])
            areas.append({'key': k, 'name': p['name'], 'plate': E.plate_of_place(a, p),
                          'flagged': bool((p if a['places'] else a).get('needsCouncilChoice')),
                          'rule': (p if a['places'] else a).get('plateRule', 'as-is'),
                          'compounds': real.get(E.area_key(*k), 0) if real is not None else round(count[k] * SAMPLE_FACTOR * RATIO)})

    groups = collections.defaultdict(list)
    for a in areas:
        groups[E.norm_name(a['plate'])].append(a)
    official = collections.defaultdict(list)
    for a in areas:
        official[E.norm_name(a['name'])].append(a)

    # Official names as aliases of plate names: kept when the official name maps to
    # one plate name and is not itself another area's plate name.
    claims = collections.defaultdict(set)
    for a in areas:
        ok, pk = E.norm_name(a['name']), E.norm_name(a['plate'])
        if ok != pk:
            claims[ok].add(pk)
    aliases, dropped = {}, {}
    for ok, pks in sorted(claims.items()):
        if len(pks) > 1:
            dropped[ok] = {'reason': 'claimed by two or more plate names', 'plates': sorted(pks)}
        elif ok in groups:
            dropped[ok] = {'reason': 'it is itself the plate name of other areas', 'plates': sorted(pks)}
        else:
            aliases[ok] = next(iter(pks))

    table = E.allocate_names(groups)
    names = []
    for idx, (nk, t) in enumerate(table):
        spell = collections.Counter(a['plate'] for a in groups[nk]).most_common()
        names.append({'n': nk, 'p': spell[0][0], 'i': idx + 1, 'd': t['digits'], 'q': t.get('qualifier'),
                      'b': [[f'{c}-{an:02d}-{q:03d}', s, z] for (c, an, q), s, z in t['blocks']]})
    out = {'country': 'BJ', 'version': '1.0', 'built': '2026-10-20' if real is not None else '2026-10-18',
           'note': 'National name table of PLATE names (the remembered name of an area: at most 12 characters and 2 '
                   'words). Blocks are frozen at first issue (20 October 2026), sized on the compounds actually grouped: '
                   'a block is never renumbered; a new area with an existing name gets the next block from that name\'s '
                   'spare space. Built from the OSM places of model/keys.json. '
                   'aliases: normalised official name -> normalised plate name, where the official name maps to one '
                   'plate name; aliasesDropped: official names that would be claimed by two plate names (or are '
                   'another plate name), so they do not decode.',
           'rules': {'block': 'max(200, ceil(2 x compounds / 100) x 100)', 'spare': {'4': 500, '5': 5000},
                     'digits': '4 if blocks + 500 <= 9000, else 5 if blocks + 5000 <= 90000, else qualifier'},
           'fields': {'n': 'normalised plate name', 'p': 'plate name as written', 'i': 'national name index (check digit input)', 'd': 'digits',
                      'q': 'qualifier list entry or null',
                      'b': 'blocks: [commune-arr-quartier, first number, size]'},
           'names': names}
    with open(os.path.join(REPO, 'model', 'names.json'), 'w', encoding='utf-8') as fh:
        fh.write('{\n')
        for k in ('country', 'version', 'built', 'note', 'rules', 'fields'):
            fh.write(f' {json.dumps(k)}: {json.dumps(out[k], ensure_ascii=False)},\n')
        fh.write(f' "aliases": {json.dumps(aliases, ensure_ascii=False, separators=(",", ":"))},\n')
        fh.write(f' "aliasesDropped": {json.dumps(dropped, ensure_ascii=False, separators=(",", ":"))},\n')
        fh.write(' "names": [\n')
        fh.write(',\n'.join('  ' + json.dumps(n, ensure_ascii=False, separators=(',', ':')) for n in names))
        fh.write('\n ]\n}\n')

    rep = [(nk, g) for nk, g in groups.items() if len(g) > 1]
    rep_areas = sum(len(g) for _, g in rep)
    by_n = collections.Counter(len(g) for _, g in rep)
    t_by = dict(table)
    digits = collections.Counter()
    for nk, t in table:
        digits[t['digits']] += 1
    largest = sorted(rep, key=lambda kv: -sum(a['compounds'] for a in kv[1]))[:15]
    most = sorted(rep, key=lambda kv: -len(kv[1]))[:15]
    over = [a for a in areas if E.block_size(a['compounds']) > 8500]

    def row(nk, g):
        t = t_by[nk]
        return {'name': nk, 'spelled': sorted({a['plate'] for a in g})[:4], 'areas': len(g),
                'compounds': sum(a['compounds'] for a in g), 'blocks': sum(z for _, _, z in t['blocks']),
                'digits': t['digits']}
    plates = plate_stats(areas, groups, official, t_by, aliases, dropped)
    stats = {
        'source': ('model/keys.json code areas; the compounds grouped at first issue (20 October 2026)' if real is not None else
                   'model/keys.json code areas; 1-in-10 building sample (N-Ways building map, 2026-10-18), '
                   f'compounds = buildings x {RATIO}'),
        'sampleOutsideArrondissements': outside,
        'areas': len(areas), 'names': len(groups),
        'repeatingNames': len(rep), 'areasWithRepeatingNames': rep_areas,
        'shareOfAreasWithRepeatingNames': round(rep_areas / len(areas), 3),
        'repeatingNamesByAreaCount': {str(k): v for k, v in sorted(by_n.items())},
        'namesByDigits': {str(k): v for k, v in sorted(digits.items())},
        'repeatingNamesByDigits': {str(k): v for k, v in sorted(collections.Counter(t_by[nk]['digits'] for nk, _ in rep).items())},
        'qualified': [nk for nk, t in table if t.get('qualifier')],
        'areasOverFourDigits': {'rule': 'an area whose block exceeds 8,500 numbers has five digits',
                                'count': len(over),
                                'largest': sorted(([a['name'], a['compounds']] for a in over), key=lambda r: -r[1])[:12]},
        'largestSharedRanges': [row(nk, g) for nk, g in largest],
        'mostRepeated': [row(nk, g) for nk, g in most],
        'plateNames': plates,
    }
    with open(os.path.join(REPO, 'model', 'stats', 'name-ranges.json'), 'w', encoding='utf-8') as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in stats.items() if k not in ('mostRepeated',)}, ensure_ascii=False, indent=1))


def plate_stats(areas, groups, official, t_by, aliases, dropped):
    """Counts for the papers: names over the limit before and after, how they were
    shortened, collisions before (official names) and after (plate names)."""
    L = E.PLATE_LANG
    n = len(areas)
    over_chars = sum(1 for a in areas if E._P.plate_length(a['name']) > E._P.MAX_CHARS)
    over_words = sum(1 for a in areas if E._P.word_count(a['name'], L) > E._P.MAX_WORDS)
    over_any = sum(1 for a in areas if not E.plate_ok(a['name']))
    rules = collections.Counter(a['rule'] for a in areas)
    flagged = [a for a in areas if a['flagged']]
    still = [a for a in flagged if not E.plate_ok(a['plate'])]

    def collide(gs):
        rep = [g for g in gs.values() if len(g) > 1]
        return {'names': len(gs), 'sharedNames': len(rep), 'areasInSharedNames': sum(len(g) for g in rep)}
    before = collide(official)
    after = collide(groups)
    newly = [nk for nk, g in groups.items() if len(g) > 1 and len({E.norm_name(a['name']) for a in g}) > 1]
    by_digits = collections.Counter()
    areas_by_digits = collections.Counter()
    for nk, t in t_by.items():
        by_digits[t['digits']] += 1
        areas_by_digits[t['digits']] += len(t['blocks'])
    big = max(t_by.items(), key=lambda kv: sum(z for _, _, z in kv[1]['blocks']))

    def code(a):
        t = t_by[E.norm_name(a['plate'])]
        first = next(f for k, f, _ in t['blocks'] if k == a['key'])
        return f"{a['plate']} · {E.spoken_number(first)}"
    ok_areas = [a for a in areas if E.plate_ok(a['plate'])]
    longest = max(ok_areas, key=lambda a: (E._P.plate_length(code(a)), code(a)))
    longest_nf = max((a for a in ok_areas if not a['flagged']), key=lambda a: (E._P.plate_length(code(a)), code(a)))
    return {
        'rule': 'plate name: at most 12 characters (accented letter, space, hyphen, apostrophe = 1) and 2 words '
                '(linking words de, du, des, la, le, les, l\', es... do not count); tools/bj_plates.py',
        'areas': n,
        'officialOverLimit': {'chars': over_chars, 'words': over_words, 'either': over_any},
        'plateRules': dict(sorted(rules.items())),
        'needsCouncilChoice': len(flagged),
        'needsCouncilChoiceWithCandidates': sum(1 for a in flagged if E.plate_ok(a['plate'])),
        'stillOverLimit': len(still),
        'stillOverLimitExamples': sorted({a['plate'] for a in still})[:12],
        'collisionsBefore': before, 'collisionsAfter': after,
        'namesSharedOnlyAfterShortening': len(newly),
        'aliases': len(aliases), 'aliasesDropped': len(dropped),
        'namesByDigits': {str(k): v for k, v in sorted(by_digits.items())},
        'areasByDigits': {str(k): v for k, v in sorted(areas_by_digits.items())},
        'biggestSharedRange': {'name': big[1] and next(a['plate'] for a in groups[big[0]]), 'areas': len(big[1]['blocks']),
                               'numbersInBlocks': sum(z for _, _, z in big[1]['blocks']), 'digits': big[1]['digits']},
        'longestCode': {'code': code(longest), 'length': E._P.plate_length(code(longest))},
        'longestCodeNotFlagged': {'code': code(longest_nf), 'length': E._P.plate_length(code(longest_nf))},
    }


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
