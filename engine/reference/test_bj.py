#!/usr/bin/env python3
"""Tests for the Benin engine (offline, standard library only).

  python3 engine/reference/test_bj.py
"""
import json
import math
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bj_engine as E  # noqa: E402
import bj_border as B  # noqa: E402

with open(os.path.join(HERE, 'test_vectors.json'), encoding='utf-8') as _fh:
    V = json.load(_fh)


def dist_m(a, b):
    return math.hypot((a[1] - b[1]) * 111320 * math.cos(math.radians(a[0])), (a[0] - b[0]) * 110574)


class Damm(unittest.TestCase):
    def test_vectors(self):
        for v in V['damm']:
            self.assertEqual(E.damm(v['digits']), v['check'])

    def test_catches_single_errors_and_adjacent_swaps(self):
        rnd = random.Random(7)
        for _ in range(300):
            d = ''.join(rnd.choice('0123456789') for _ in range(9))
            full = d + str(E.damm(d))
            for i in range(len(full)):
                for c in '0123456789':
                    if c != full[i]:
                        self.assertFalse(E.damm_ok(full[:i] + c + full[i + 1:]))
            for i in range(len(full) - 1):
                if full[i] != full[i + 1]:
                    self.assertFalse(E.damm_ok(full[:i] + full[i + 1] + full[i] + full[i + 2:]))


class Utm(unittest.TestCase):
    def test_vectors_match_gdal(self):
        # utm31n values in the vectors were checked against GDAL (EPSG:4326 -> EPSG:32631) to the millimetre.
        for v in V['spot']:
            e, n = E.to_utm(v['lat'], v['lon'])
            self.assertAlmostEqual(e, v['utm31n'][0], places=2)
            self.assertAlmostEqual(n, v['utm31n'][1], places=2)

    def test_round_trip(self):
        for v in V['spot']:
            lat, lon = E.from_utm(*E.to_utm(v['lat'], v['lon']))
            self.assertLess(dist_m((lat, lon), (v['lat'], v['lon'])), 0.001)

    def test_zone_origin(self):
        e, n = E.to_utm(0.0, 3.0)
        self.assertAlmostEqual(e, 500000.0, places=3)
        self.assertAlmostEqual(n, 0.0, places=3)


class Spot(unittest.TestCase):
    def test_vectors(self):
        for v in V['spot']:
            s = E.spot_encode(v['lat'], v['lon'])
            self.assertEqual(s['machine'], v['spot'], v['label'])
            self.assertEqual(s['display'], v['spotDisplay'])
            a = E.code_area(v['lat'], v['lon'])
            self.assertEqual(a['quartierName'], v['area']['quartierName'])

    def test_decode_within_cell(self):
        for v in V['spot']:
            lat, lon = E.spot_decode(v['spot'])
            self.assertAlmostEqual(lat, v['decoded'][0], places=7)
            self.assertAlmostEqual(lon, v['decoded'][1], places=7)
            self.assertLess(dist_m((lat, lon), (v['lat'], v['lon'])), 3 * math.sqrt(2) / 2 + 0.01)
            self.assertEqual(E.spot_decode(v['spotDisplay']), (lat, lon))

    def test_rejects_bad(self):
        with self.assertRaises(ValueError):
            E.spot_decode('BJ-COT-09-S-35986')
        with self.assertRaises(ValueError):
            E.spot_encode(5.0, 2.0)  # at sea
        with self.assertRaises(ValueError):
            E.spot_encode(13.0, 2.5)  # Niger, more than 10 km from every outline

    def test_outside_every_outline(self):
        # Monsey, Karimama: an issued compound 1.4 km beyond the outline, in Monsey's frame
        lat, lon = 12.2796011, 2.9817464
        self.assertIsNone(E.arrondissement_at(lat, lon))
        s = E.spot_encode(lat, lon)
        self.assertEqual((s['machine'], s['display']), ('BJ-KAR-05-S-349RVMVH', 'KAR 05 · 349 RVMVH'))
        self.assertLess(dist_m(E.spot_decode(s['machine']), (lat, lon)), 3 * math.sqrt(2) / 2 + 0.01)
        # Atchannou, Athiémé: an issued compound west of every frame takes the nearest cell of its frame
        lat, lon = 6.5089835, 1.6966827
        self.assertEqual(E.spot_encode(lat, lon)['display'], 'ATH 01 · C22 2W2')
        self.assertLess(dist_m(E.spot_decode('ATH 01 · C22 2W2'), (lat, lon)), 112)
        # a spot code is decoded in the arrondissement it names, with no lookup
        self.assertEqual(E.spot_arrondissement_of('BJ-ATH-01-S-C222W2')[0]['name'], 'Atchannou')


class Conformance(unittest.TestCase):
    """engine/reference/vectors.json, the vectors every port must reproduce."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, 'vectors.json'), encoding='utf-8') as fh:
            cls.v = json.load(fh)

    def test_spots(self):
        for c in self.v['spots']:
            s = E.spot_encode(c['lat'], c['lon'])
            self.assertEqual((s['machine'], s['display']), (c['machine'], c['display']))
            self.assertEqual(list(E.spot_decode(s['display'])), c['decoded'])

    def test_spots_outside_every_outline(self):
        issued = 0
        for c in self.v['spotsOutside']:
            self.assertIsNone(E.arrondissement_at(c['lat'], c['lon']))
            if 'error' in c:
                self.assertIsNone(E.spot_arrondissement(c['lat'], c['lon']))
                with self.assertRaises(ValueError):
                    E.spot_encode(c['lat'], c['lon'])
                continue
            issued += 'issued' in c
            a = E.spot_arrondissement(c['lat'], c['lon'])
            self.assertEqual('%s-%02d' % (a['commune'], a['number']), c['arrondissement'])
            s = E.spot_encode(c['lat'], c['lon'])
            self.assertEqual((s['machine'], s['display']), (c['machine'], c['display']))
            self.assertEqual(list(E.spot_decode(s['machine'])), c['decoded'])
        self.assertGreaterEqual(issued, 400)


class Codes(unittest.TestCase):
    def test_machine(self):
        for v in V['machine']:
            self.assertEqual(E.machine(*v['parts']), v['code'])
            p = E.parse_machine(v['code'])
            self.assertEqual([p['commune'], p['arrondissement'], p['quartier'], p['number']], v['parts'])

    def test_machine_detects_typo(self):
        with self.assertRaises(ValueError):
            E.parse_machine('BJ-COT-09-004-4871-0')  # 17 -> 71 swapped
        with self.assertRaises(ValueError):
            E.parse_machine('BJ-COT-09-005-4817-0')  # area digit changed: 4817 is not in that area's blocks

    def test_remembered(self):
        for v in V['remembered']:
            self.assertEqual(list(E.parse_remembered(v['text'])), v['parsed'])
        self.assertEqual(E.remembered('Zogbo', 4817), 'Zogbo · 48 17')

    def test_official_first(self):
        rec = {'official': {'text': 'N° 43, Rue 12.217'}, 'areaName': 'Haie Vive', 'number': 1234}
        self.assertEqual(E.display_address(rec), ('N° 43, Rue 12.217', 'official'))
        self.assertEqual(E.display_address({'official': None, 'areaName': 'Zogbo', 'number': 4817, 'interim': True}),
                         ('Zogbo · 48 17', 'nways-interim'))
        self.assertEqual(E.display_address({'areaName': 'Zogbo', 'number': 4817}), ('Zogbo · 48 17', 'nways'))

    def test_spoken(self):
        for v in V['spokenFr']:
            self.assertEqual(E.say_fr(v['number']), v['fr'])


class Compounds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comps, cls.nums = E.demo()

    def test_counts(self):
        cs = V['compoundSample']
        self.assertEqual(sum(len(c['structures']) for c in self.comps), cs['structures'])
        self.assertEqual(len(self.comps), cs['compounds'])

    def test_sample_numbers(self):
        by_centroid = {tuple(self.comps[i]['centroid']): (a, n) for i, (a, n) in self.nums.items()}
        for s in V['compoundSample']['sample']:
            a, n = by_centroid[tuple(s['centroid'])]
            self.assertEqual(n, s['number'])
            self.assertEqual(E.machine(a['commune'], a['arrondissement'], a['quartier'], n), s['machine'])

    def test_every_structure_in_one_compound(self):
        ids = [s['id'] for c in self.comps for s in c['structures']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_numbers_unique_per_area_and_leave_gaps(self):
        per = {}
        for a, n in self.nums.values():
            per.setdefault((a['commune'], a['arrondissement'], a['quartier']), []).append(n)
        for k, ns in per.items():
            self.assertEqual(len(ns), len(set(ns)))
            first, size = E.area_blocks(*k)[1][0]
            self.assertTrue(all(first <= n < first + (size * 2) // 3 for n in ns),
                            'main part of the block only; its top third is the tail reserve')

    def test_provisional(self):
        p = V['compoundSample']['provisional']
        members = {n: tuple(self.comps[i]['centroid']) for i, (a, n) in self.nums.items()
                   if [a['commune'], a['arrondissement'], a['quartier']] == p['area']}
        got = E.provisional_number(members, tuple(p['areaBox']), p['lon'], p['lat'], block=tuple(p['block']))
        self.assertEqual(tuple(p['block']), E.area_blocks(*p['area'])[1][0])
        self.assertEqual(got, p['number'])
        self.assertNotIn(got, members)

    def test_provisional_full_gap_uses_tail(self):
        box = (0.0, 0.0, 1.0, 1.0)
        existing = {1000: (0.1, 0.1), 1001: (0.2, 0.1)}
        # 1000 and 1001 are adjacent: nothing free between them, so the tail reserve is used
        n = E.provisional_number(existing, box, 0.15, 0.1)
        self.assertNotIn(n, existing)
        self.assertTrue(n >= 7000 or n > 1001)


class NationalNames(unittest.TestCase):
    """The remembered form alone is unique in all of Benin (SPEC 7.1)."""

    def test_normalisation(self):
        for v in V['normalised']:
            self.assertEqual(E.norm_name(v['name']), v['key'], v['name'])
        self.assertEqual(E.norm_name('Gbèdji'), E.norm_name('Gbedji'))
        self.assertEqual(E.norm_name('Ganvié I'), E.norm_name('Ganvié 1'))
        self.assertEqual(E.norm_name('Ouèssè'), E.norm_name('Wèssè'))
        self.assertNotEqual(E.norm_name('Ganvié 1'), E.norm_name('Ganvié 2'))

    def test_same_name_decodes_to_different_places(self):
        got = {v['text']: E.decode_remembered(v['text']) for v in V['sameName']}
        for v in V['sameName']:
            d = got[v['text']]
            self.assertEqual(d['machine'], v['machine'], v['text'])
            self.assertEqual([d['commune'], d['arrondissement'], d['quartier']],
                             [v['commune'], v['arrondissement'], v['quartier']])
        by_name = {}
        for v in V['sameName']:
            by_name.setdefault(E.norm_name(v['text'].split(' · ')[0]), []).append(got[v['text']])
        for k, ds in by_name.items():
            self.assertEqual(len(ds), 2, k)
            self.assertNotEqual((ds[0]['commune'], ds[0]['arrondissement'], ds[0]['quartier']),
                                (ds[1]['commune'], ds[1]['arrondissement'], ds[1]['quartier']), k)
            self.assertNotEqual(ds[0]['machine'], ds[1]['machine'], k)

    def test_spelling_variants_reach_the_same_range(self):
        t = next(v['text'] for v in V['sameName'] if E.norm_name(v['text'].split(' · ')[0]) == 'gbeji')
        name, num = t.split(' · ')
        for variant in ('Gbédji', 'GBEDJI', 'Gbedji'):
            self.assertEqual(E.decode_remembered(f'{variant} {num.replace(" ", "")}')['machine'], E.decode_remembered(t)['machine'])

    def test_not_issued_and_wrong_commune(self):
        for t in V['notIssued']:
            with self.assertRaises(ValueError, msg=t):
                E.decode_remembered(t)
        v = V['sameName'][0]
        right = E.decode_remembered(v['text'])
        other = next(c['name'] for c in E.keys()['communes'] if c['key'] != right['commune'])
        with self.assertRaises(ValueError):
            E.decode_remembered(f"{v['text']}, {other}")
        self.assertEqual(E.decode_remembered(f"{v['text']}, {right['communeName']}")['commune'], right['commune'])

    def test_table_blocks_disjoint_and_in_range(self):
        t = E.names()
        seen_idx = set()
        for e in t['names']:
            self.assertNotIn(e['i'], seen_idx)
            seen_idx.add(e['i'])
            lo, hi = 10 ** (e['d'] - 1), 10 ** e['d']
            spans = sorted((f, f + z) for _, f, z in e['b'])
            self.assertGreaterEqual(spans[0][0], lo)
            self.assertLessEqual(spans[-1][1] + E.SPARE[e['d']], hi, e['n'])
            for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
                self.assertLessEqual(a1, b0, e['n'])
            self.assertLessEqual(e['d'], 5)
        self.assertEqual(len({ak for e in t['names'] for ak, _, _ in e['b']}), sum(len(e['b']) for e in t['names']))

    def test_check_digit_catches_typos_across_same_named_areas(self):
        """A single wrong digit or adjacent swap in the number never lands silently in
        another area of the same name: either no block holds it or the check differs."""
        for nk in ('zongo', 'agata', 'gbeji', 'fifaji', 'ganvie1'):
            e = E.names()['_byName'][nk]
            for _, first, size in e['b']:
                for num in range(first, first + size, 7):
                    c = E.check_digit(e['i'], num)
                    s = str(num)
                    typos = {s[:i] + d + s[i + 1:] for i in range(len(s)) for d in '0123456789'} | \
                            {s[:i] + s[i + 1] + s[i] + s[i + 2:] for i in range(len(s) - 1)}
                    for t in typos - {s}:
                        if t[0] == '0':
                            continue
                        try:
                            E.resolve(nk, int(t))
                        except ValueError:
                            continue
                        self.assertNotEqual(E.check_digit(e['i'], int(t)), c, f'{nk} {s} -> {t}')

    def test_new_area_gets_a_block_from_spare_and_old_blocks_stay(self):
        e = E.names()['_byName']['zongo']
        before = [list(b) for b in e['b']]
        first, size = E.next_block(e, 140)
        self.assertEqual(size, 300)
        self.assertGreaterEqual(first, max(f + z for _, f, z in e['b']))
        self.assertLessEqual(first + size, 10 ** e['d'])
        self.assertEqual(before, [list(b) for b in e['b']])


class PlateNames(unittest.TestCase):
    """The name in a remembered code is at most 12 characters and 2 words (SPEC 7.2)."""

    def test_length_and_words(self):
        for v in V['plateLength']:
            self.assertEqual(E._P.plate_length(v['name']), v['length'], v['name'])
            self.assertEqual(E._P.word_count(v['name'], E.PLATE_LANG), v['words'], v['name'])
            self.assertEqual(E.plate_ok(v['name']), v['ok'], v['name'])

    def test_plate_of_long_official_name(self):
        for v in V['plateNames']:
            c, a, q = v['area']
            arr = E.keys()['_byCode'][(c, a)]
            place = next((p for p in arr['places'] if p['index'] == q), None) or {'index': 0, 'name': arr['name']}
            self.assertEqual(place['name'], v['official'])
            self.assertEqual(E.plate_of_place(arr, place), v['plate'])
            self.assertEqual(E.plate_ok(v['plate']), not v['needsCouncilChoice'] or bool(v.get('candidates')), v['plate'])

    def test_official_name_still_decodes(self):
        for v in V['officialAlias']:
            self.assertEqual(E.decode_remembered(v['official'])['machine'], v['machine'], v['official'])
            self.assertEqual(E.decode_remembered(v['plate'])['machine'], v['machine'], v['plate'])
        # the abbreviation expands back: the full saint's name typed decodes
        self.assertEqual(E.norm_name('St Prosper'), E.norm_name('Saint Prosper'))

    def test_collision_after_shortening_decodes_apart(self):
        for a, b in V['collideAfterShortening']:
            self.assertEqual(E.norm_name(a['text'].split(' · ')[0]), E.norm_name(b['text'].split(' · ')[0]))
            self.assertNotEqual(E.norm_name(a['official']), E.norm_name(b['official']))
            da, db = E.decode_remembered(a['text']), E.decode_remembered(b['text'])
            self.assertEqual(da['machine'], a['machine'])
            self.assertEqual(db['machine'], b['machine'])
            self.assertNotEqual(da['communeName'], db['communeName'])

    def test_provisional_names_decode_and_unflagged_long_names_refused(self):
        # every home has its code: an area waiting for its commune's choice decodes
        # under its provisional name; only an unflagged long name is refused
        for t in V['plateRefused']:
            self.assertTrue(E.decode_remembered(t)['machine'].startswith('BJ-'), t)
        self.assertEqual(E.remembered('Tchanhounkpamè', 1000, provisional=True), 'Tchanhounkpamè · 10 00')
        with self.assertRaises(ValueError):
            E.remembered('Camp Peulh Soukoumpérou', 1001)
        self.assertEqual(E.remembered('Soukoumpérou', 1001), 'Soukoumpérou · 10 01')

    def test_every_plate_in_table_fits_or_is_flagged(self):
        flagged = set()
        for a in E.keys()['arrondissements']:
            for p in a['places'] or [a]:
                rec = p
                idx = p.get('index', 0) if a['places'] else 0
                if rec.get('needsCouncilChoice'):
                    flagged.add(E.area_key(a['commune'], a['number'], idx))
                elif not E.plate_ok(E.plate_of_place(a, p if a['places'] else {'index': 0, 'name': a['name']})):
                    self.fail(f"{a['commune']}-{a['number']} {p.get('name')}: plate over the limit and not flagged")
        self.assertTrue(flagged)

    def test_aliases_point_to_one_plate_name(self):
        t = E.names()
        for alias, pk in t['aliases'].items():
            self.assertIn(pk, t['_byName'])
            self.assertNotIn(alias, t['_byName'])
        for alias in t['aliasesDropped']:
            self.assertNotIn(alias, t['aliases'])


class Hilbert(unittest.TestCase):
    def test_bijective_small(self):
        seen = {E.hilbert_d(3, x, y) for x in range(8) for y in range(8)}
        self.assertEqual(seen, set(range(64)))

    def test_neighbours_adjacent(self):
        pos = {E.hilbert_d(3, x, y): (x, y) for x in range(8) for y in range(8)}
        for d in range(63):
            (x1, y1), (x2, y2) = pos[d], pos[d + 1]
            self.assertEqual(abs(x1 - x2) + abs(y1 - y2), 1)



class Border(unittest.TestCase):
    """SPEC 1b: the national border decides, with the simplification margin."""

    def test_square(self):
        b = B.Border([[(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.1)]])
        self.assertTrue(b.contains(0.05, 0.05))
        self.assertEqual(b.outside_m(0.05, 0.05), 0.0)
        self.assertAlmostEqual(b.outside_m(0.05, 0.1 + 300 / 111320.0), 300.0, places=3)
        self.assertFalse(b.beyond(0.05, 0.1 + 299 / 111320.0))
        self.assertTrue(b.beyond(0.05, 0.1 + 301 / 111320.0))
        self.assertTrue(B.Border(b_rings(b), 50).abroad(0.05, 0.1 + 251 / 111320.0))

    def test_benin(self):
        self.assertFalse(B.abroad(6.37, 2.43))             # Cotonou
        self.assertFalse(B.abroad(6.45, 2.708))            # 150 m outside: within 300 m
        self.assertTrue(B.abroad(6.42, 2.76))              # a neighbouring country, though it has a spot code
        self.assertIsNotNone(E.spot_arrondissement(6.42, 2.76))
        self.assertTrue(B.abroad(8.32, 1.62))              # a neighbouring country, though in an arrondissement outline
        self.assertIsNotNone(E.arrondissement_at(8.32, 1.62))


def b_rings(b):
    return [[(x1, y1) for x1, y1, _x2, _y2 in b.segs]]


if __name__ == '__main__':
    unittest.main(verbosity=1)
