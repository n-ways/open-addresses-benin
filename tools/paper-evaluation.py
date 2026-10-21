#!/usr/bin/env python3
"""The measured properties of the paper's evaluation chapter: model/stats/evaluation.json.

  python3 tools/paper-evaluation.py

Reads every row of registry/ once, with the reference engine. Standard library only;
about 1 GB of memory for the two uniqueness sets.

  uniqueness    machine forms and remembered forms (name key + number) that occur twice
  lengths       characters of the written form ("Cadjéhoun · 18 07"), and of the plate name
  decode        every 20th row: the written form decoded alone gives back its machine form,
                and the machine form parses with its check digit
  typos         every 100th row: each single wrong digit and each swap of two neighbouring
                digits in the number of the written form, and what it lands on (another
                issued code of the same name, an unissued number inside a block, or a number
                outside every block of the name, which is refused); the same errors in the
                machine form, all of which the check digit must catch
  spot          every 20th row whose entrance lies in its spot frame: the centre of the published
                spot code against the entrance; and every row whose entrance lies beyond every
                frame, so that its spot code names the nearest cell of a frame (SPEC 2.4)
"""
import collections, csv, glob, gzip, json, math, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402


def variants(num):
    s = str(num)
    out = []
    for i, ch in enumerate(s):
        for d in '0123456789':
            if d != ch and not (i == 0 and d == '0'):
                out.append(('substitution', int(s[:i] + d + s[i + 1:])))
    for i in range(len(s) - 1):
        if s[i] != s[i + 1] and not (i == 0 and s[i + 1] == '0'):
            out.append(('transposition', int(s[:i] + s[i + 1] + s[i] + s[i + 2:])))
    return out


def metres(a, b):
    lat0 = math.radians((a[0] + b[0]) / 2)
    return math.hypot((a[0] - b[0]) * 110574, (a[1] - b[1]) * 111320 * math.cos(lat0))


def main():
    names = E.names()
    areas = {}
    with gzip.open(os.path.join(REPO, 'registry', 'areas.csv.gz'), 'rt', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            areas[r['zone']] = r
    machines, homes = set(), set()
    dup_machine = dup_home = 0
    written_len, plate_len = collections.Counter(), collections.Counter()
    decoded = decode_fail = 0
    spot_d, spot_fail = [], []
    no_spot = collections.Counter()
    beyond, beyond_d = collections.Counter(), []
    bound = 3 * math.sqrt(2) / 2 + 0.01   # half the diagonal of a 3 m cell, with the projection's rounding
    sample_typos = []
    issued_by_name = collections.defaultdict(set)
    n = 0
    files = sorted(p for p in glob.glob(os.path.join(REPO, 'registry', '*.csv.gz')) if not p.endswith('areas.csv.gz'))
    for path in files:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                n += 1
                a = areas[r['zone']]
                if r['machine'] in machines:
                    dup_machine += 1
                machines.add(r['machine'])
                hk = (a['name_key'], int(r['number']))
                if hk in homes:
                    dup_home += 1
                homes.add(hk)
                issued_by_name[a['name_key']].add(int(r['number']))
                written_len[len(r['written'])] += 1
                entrance = (float(r['entrance_lat']), float(r['entrance_lng']))
                spot_m = None
                if not r['spot_code']:
                    no_spot[r['zone'][:3]] += 1
                else:
                    spot_m = metres(E.spot_decode(r['spot_code']), entrance)
                    if spot_m > bound:
                        beyond[r['zone'][:3]] += 1
                        beyond_d.append(spot_m)
                plate_len[len(a['plate_name'])] += 1
                if n % 20 == 0:
                    try:
                        ok = E.decode_remembered(r['written'])['machine'] == r['machine']
                        E.parse_machine(r['machine'])
                    except ValueError:
                        ok = False
                    decoded += ok
                    decode_fail += not ok
                    if spot_m is None:
                        spot_fail.append((r['machine'], r['spot_code'], 'no spot code'))
                    elif spot_m <= bound:
                        spot_d.append(spot_m)
                if n % 100 == 0:
                    sample_typos.append((a['name_key'], int(r['number']), r['machine'],
                                         r['zone'], float(r['entrance_lat']), float(r['entrance_lng'])))
    typos = {k: collections.Counter() for k in ('substitution', 'transposition')}
    machine_caught = machine_total = 0
    wrong = []   # (name key, mistyped number, zone and point of the intended code)
    for nk, num, mach, zone, lat, lng in sample_typos:
        e = names['_byName'][nk]
        blocks = [(f, f + z) for _, f, z in e['b']]
        head = mach.rsplit('-', 2)[0]
        for kind, v in variants(num):
            if v in issued_by_name[nk]:
                typos[kind]['another issued code'] += 1
                wrong.append((nk, v, zone, lat, lng))
            elif len(str(v)) == e['d'] and any(lo <= v < hi for lo, hi in blocks):
                typos[kind]['unissued number in a block'] += 1
            else:
                typos[kind]['outside every block (refused)'] += 1
            machine_total += 1
            try:
                E.parse_machine(f'{head}-{v}-{mach[-1]}')
            except ValueError:
                machine_caught += 1
    # where a mistyped remembered code that is another issued code leads: second pass for its points
    want = {(nk, v) for nk, v, _, _, _ in wrong}
    where = {}
    for path in files:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                k = (areas[r['zone']]['name_key'], int(r['number']))
                if k in want:
                    where[k] = (r['zone'], float(r['entrance_lat']), float(r['entrance_lng']))
    dist, same_area = [], 0
    for nk, v, zone, lat, lng in wrong:
        z, la, ln = where[(nk, v)]
        same_area += z == zone
        dist.append(metres((lat, lng), (la, ln)))
    dist.sort()
    lens = sorted(written_len.elements())
    out = {
        'built': '2026-10-21',
        'note': 'From registry/ and engine/reference/bj_engine.py (tools/paper-evaluation.py).',
        'codes': n,
        'duplicateMachineForms': dup_machine,
        'duplicateRememberedForms': dup_home,
        'writtenLength': {'min': lens[0], 'median': statistics.median(lens), 'p90': lens[int(0.9 * (len(lens) - 1))],
                          'max': lens[-1], 'byLength': dict(sorted(written_len.items()))},
        'plateLengthByCodes': dict(sorted(plate_len.items())),
        'decode': {'sampled': decoded + decode_fail, 'exact': decoded, 'failed': decode_fail},
        'typos': {'sampledCodes': len(sample_typos),
                  **{k: dict(v) for k, v in typos.items()},
                  'landingOnAnotherCode': {'count': len(dist), 'sameArea': same_area,
                                           'distanceM': {'p25': round(dist[len(dist) // 4]), 'median': round(dist[len(dist) // 2]),
                                                         'p75': round(dist[3 * len(dist) // 4]), 'p90': round(dist[9 * len(dist) // 10])}},
                  'machineFormErrors': machine_total, 'machineFormErrorsCaught': machine_caught},
        'withoutSpotCode': {'codes': sum(no_spot.values()), 'byCommune': dict(no_spot.most_common())},
        'spotBeyondFrame': {'codes': sum(beyond.values()), 'byCommune': dict(beyond.most_common()),
                            'maxM': round(max(beyond_d), 1) if beyond_d else None},
        'spot': {'sampled': len(spot_d) + len(spot_fail), 'failed': len(spot_fail), 'failedExamples': spot_fail[:5], 'medianM': round(statistics.median(spot_d), 2),
                 'maxM': round(max(spot_d), 2), 'p99M': round(sorted(spot_d)[int(0.99 * (len(spot_d) - 1))], 2)},
    }
    with open(os.path.join(REPO, 'model', 'stats', 'evaluation.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
