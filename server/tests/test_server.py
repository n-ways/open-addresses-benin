"""Tests of the registry server: import and export, every endpoint, and issuing.

The fixture (server/testdata/registry) is the published area table and the real
codes of one commune, Covè. server/testdata/parity.json holds results computed
with the N-Ways issuer itself for the same state: the numbers, codes and blocks it
gives a sequence of new homes and doors, and the code area, nearest area, spot code
and Plus Code of 400 points. The server must reproduce every one.

Run: python3 -m unittest discover -s server/tests   (from the repository root)
"""
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from server import api, store  # noqa: E402
from server import engine as X  # noqa: E402

FIXTURE = os.path.join(REPO, 'server', 'testdata', 'registry')
PARITY = os.path.join(REPO, 'server', 'testdata', 'parity.json')
GAPS = os.path.join(REPO, 'server', 'testdata', 'gaps.csv')
KEY = 'test-issuing-key'


def quiet(*_):
    pass


def read_json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh)


def unzip(path):
    with gzip.open(path, 'rb') as fh:
        return fh.read()


class Served(object):
    """A server on a fresh import of the fixture, on a free local port."""

    def __init__(self, keys=(KEY,), per_day=10000, registry=None):
        self.dir = tempfile.mkdtemp(prefix='nways-bj-')
        self.db = os.path.join(self.dir, 'addresses.sqlite')
        store.import_registry(self.db, registry(self.dir) if registry else FIXTURE, log=quiet)
        self.app = api.App(api.Config(self.db, keys=keys, per_day=per_day, cors=['*']))
        self.srv = api.make_server(self.app, '127.0.0.1', 0)
        self.srv.RequestHandlerClass.log_message = lambda *a: None
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def call(self, method, path, body=None, key=KEY, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request('http://127.0.0.1:%d%s' % (self.port, path), data=data, method=method)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        if key:
            req.add_header('Authorization', 'Bearer ' + key)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read().decode()), dict(r.headers)
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read().decode()), dict(e.headers)

    def get(self, path):
        s, b, _ = self.call('GET', path, key=None)
        return s, b

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.app.store.close()
        shutil.rmtree(self.dir)


def first_rows(n=5):
    with gzip.open(os.path.join(FIXTURE, 'COV.csv.gz'), 'rt', encoding='utf-8') as fh:
        lines = [next(fh) for _ in range(n + 1)]
    import csv
    return list(csv.DictReader(lines))


# ---------------------------------------------------------------------- import and export

class ImportExport(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='nways-bj-')
        self.db = os.path.join(self.dir, 'a.sqlite')

    def tearDown(self):
        shutil.rmtree(self.dir)

    def copy_fixture(self):
        d = os.path.join(self.dir, 'registry')
        shutil.copytree(FIXTURE, d)
        return d

    def test_round_trip_is_byte_identical(self):
        n = store.import_registry(self.db, FIXTURE, log=quiet)
        self.assertEqual(n, 5903)
        out = os.path.join(self.dir, 'out')
        store.export_registry(self.db, out, log=quiet)
        self.assertEqual(sorted(os.listdir(out)), sorted(os.listdir(FIXTURE)))
        for f in ('areas.csv.gz', 'COV.csv.gz'):
            self.assertEqual(unzip(os.path.join(out, f)), unzip(os.path.join(FIXTURE, f)), f)
        with open(os.path.join(out, 'MANIFEST.json'), 'rb') as a, open(os.path.join(FIXTURE, 'MANIFEST.json'), 'rb') as b:
            self.assertEqual(a.read(), b.read())

    def test_reimport_is_safe(self):
        store.import_registry(self.db, FIXTURE, log=quiet)
        self.assertEqual(store.import_registry(self.db, FIXTURE, log=quiet), 5903)
        self.assertEqual(store.import_registry(self.db, FIXTURE, force=True, log=quiet), 5903)
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute('SELECT count(*) FROM codes').fetchone()[0], 5903)
        self.assertEqual(c.execute('SELECT count(*) FROM codes_rtree').fetchone()[0], 5903)
        c.close()

    def test_changed_file_is_refused_and_nothing_changes(self):
        store.import_registry(self.db, FIXTURE, log=quiet)
        d = self.copy_fixture()
        raw = unzip(os.path.join(d, 'COV.csv.gz')).replace(b'Abayaho', b'Abayaxo', 1)
        with gzip.open(os.path.join(d, 'COV.csv.gz'), 'wb') as fh:
            fh.write(raw)
        with self.assertRaises(store.ImportError_) as cm:
            store.import_registry(self.db, d, force=True, log=quiet)
        self.assertIn('SHA-256', str(cm.exception))
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT count(*) FROM codes WHERE home LIKE 'Abayaxo%'").fetchone()[0], 0)
        self.assertEqual(c.execute('SELECT count(*) FROM codes').fetchone()[0], 5903)
        c.close()

    def test_wrong_count_and_unlisted_file_are_refused(self):
        d = self.copy_fixture()
        man = read_json(os.path.join(d, 'MANIFEST.json'))
        man['byUnit']['COV'] += 1
        man['codes'] += 1
        write_json(os.path.join(d, 'MANIFEST.json'), man)
        with self.assertRaises(store.ImportError_):
            store.import_registry(self.db, d, log=quiet)
        d2 = os.path.join(self.dir, 'r2')
        shutil.copytree(FIXTURE, d2)
        shutil.copy(os.path.join(d2, 'COV.csv.gz'), os.path.join(d2, 'XXX.csv.gz'))
        with self.assertRaises(store.ImportError_):
            store.import_registry(self.db, d2, log=quiet)

    def test_csv_dialect(self):
        self.assertEqual(store.csv_line(['a', '', 'b,c', 'say "hi"', ' x']), 'a,,"b,c","say ""hi"""," x"\n')


# ---------------------------------------------------------------------- parity with the N-Ways issuer

class Parity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parity = read_json(PARITY)
        cls.dir = tempfile.mkdtemp(prefix='nways-bj-')
        db = os.path.join(cls.dir, 'a.sqlite')
        store.import_registry(db, FIXTURE, log=quiet)
        cls.conn = store.connect(db)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        shutil.rmtree(cls.dir)

    def test_numbers_codes_and_blocks(self):
        for s in self.parity['scenarios']:
            reg = store.load_areas(self.conn)
            orig = reg.by_zone[s['zone']]
            a = orig.copy()
            issued = [(int(n), la, lo) for n, la, lo in s['issued']]
            pts = [tuple(p) for p in s.get('points') or []] + [(d['lat'], d['lng']) for d in s.get('doors') or []]
            self.assertEqual(len(pts), len(s['want']))
            for (lat, lng), want in zip(pts, s['want']):
                nb = len(a.blocks)
                n = reg.insert(a, issued, lat, lng)
                if want.get('full'):
                    self.assertIsNone(n, s['name'])
                    continue
                for b in a.blocks[nb:]:
                    reg.add_block(a.zone, b)
                f = reg.forms(a, n)
                got = {'number': n, 'machine': f['machine'], 'home': f['home'], 'written': f['written'], 'blocks': a.blocks}
                self.assertEqual(got, want, s['name'])
                issued.append((n, lat, lng))
        names = [s['name'] for s in self.parity['scenarios']]
        self.assertTrue(any(len(s['want'][-1]['blocks']) > 1 for s in self.parity['scenarios']), names)

    def test_area_spot_and_plus_code_of_points(self):
        reg = store.load_areas(self.conn)
        for g in self.parity['geo']:
            a = reg.area_at(g['lat'], g['lng'])
            self.assertEqual(a.zone if a else None, g.get('area'), g)
            self.assertEqual(reg.nearest_area(g['lat'], g['lng']).zone, g['nearest'], g)
            self.assertEqual(X.spot_display(g['lat'], g['lng']) or None, g.get('spot'), g)
            self.assertEqual(X.plus_code(g['lat'], g['lng']), g['plus'], g)

    def test_registry_rows_reproduce(self):
        """Every published row's forms, check digit and spot code come out of the rules."""
        reg = store.load_areas(self.conn)
        for r in self.conn.execute('SELECT * FROM codes'):
            a = reg.by_zone[r['zone']]
            f = reg.forms(a, int(r['number']))
            self.assertEqual((f['machine'], f['home'], f['written'], str(f['check'])),
                             (r['machine'], r['home'], r['written'], r['check']))
            self.assertEqual(X.spot_display(float(r['entrance_lat']), float(r['entrance_lng'])), r['spot_code'])


# ---------------------------------------------------------------------- reading

class Read(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Served()
        cls.row = first_rows(1)[0]

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def err(self, path, status, code):
        s, b = self.s.get(path)
        self.assertEqual(s, status, b)
        self.assertEqual(set(b), {'error'})
        self.assertEqual(b['error']['code'], code, b)
        self.assertTrue(b['error']['message'])

    def test_health_and_info(self):
        s, b = self.s.get('/v1/health')
        self.assertEqual((s, b['status'], b['country'], b['codes']), (200, 'ok', 'BJ', 5903))
        self.assertEqual(b['registry_exported'], '2026-10-20T19:51:08Z')
        s, b = self.s.get('/v1/info')
        self.assertEqual(s, 200)
        self.assertEqual(b['codes']['total'], 5903)
        self.assertEqual(b['areas'], 12964)
        self.assertIn('N-WAYS LIMITED', b['credit'])
        self.assertTrue(b['issuing']['enabled'])

    def test_code_card(self):
        r = self.row
        s, b = self.s.get('/v1/codes/' + r['machine'])
        self.assertEqual(s, 200)
        self.assertEqual(b['registry'], r)
        self.assertEqual(b['machine'], r['machine'])
        self.assertEqual(b['number'], int(r['number']))
        self.assertEqual(b['area']['commune'], 'Covè')
        self.assertEqual(b['spot_code'], r['spot_code'])
        self.assertEqual(b['written'], r['written'])  # people's forms carry no check digit
        self.assertNotIn('-', b['written'])
        s, b2 = self.s.get('/v1/codes/' + r['machine'].lower())
        self.assertEqual(b2['machine'], r['machine'])
        s, b3 = self.s.get('/v1/codes/' + r['machine'].rsplit('-', 1)[0])
        self.assertEqual(b3['machine'], r['machine'])

    def test_code_errors(self):
        m = self.row['machine']
        wrong = m[:-1] + str((int(m[-1]) + 1) % 10)
        self.err('/v1/codes/' + wrong, 422, 'check_digit')
        self.err('/v1/codes/nonsense', 400, 'invalid_code')
        self.err('/v1/codes/BJ-COV-04-001-1199', 404, 'not_issued')
        self.err('/v1/codes/BJ-COV-04-001-1300', 422, 'not_in_area')
        self.err('/v1/codes/BJ-ZZZ-04-001-1000', 404, 'unknown_area')

    def test_find(self):
        r = self.row
        name, num = r['home'].rsplit(' ', 1)
        plain = X.plain(name).lower()
        for q in (r['home'], r['written'], '%s %s %s' % (plain, num[:2], num[2:]), '  %s   ·%s ' % (name.upper(), num),
                  r['home'] + ', Covè', r['home'] + ', cove', r['machine'], r['spot_code']):
            s, b = self.s.get('/v1/find?q=' + urllib.request.quote(q))
            self.assertEqual(s, 200, (q, b))
            self.assertEqual(b['matches'][0]['machine'], r['machine'], q)
        s, b = self.s.get('/v1/find?q=' + urllib.request.quote(r['machine']))
        self.assertEqual(b['kind'], 'machine')

    def test_find_errors(self):
        r = self.row
        m = r['machine']
        self.err('/v1/find?q=' + m[:-1] + str((int(m[-1]) + 1) % 10), 422, 'check_digit')
        self.err('/v1/find', 400, 'missing_parameter')
        self.err('/v1/find?q=' + urllib.request.quote(r['home'] + ', Cotonou'), 404, 'wrong_commune')
        self.err('/v1/find?q=' + urllib.request.quote('Nowhereville 1000'), 404, 'unknown_name')
        self.err('/v1/find?q=' + urllib.request.quote(r['home'].rsplit(' ', 1)[0] + ' 1199'), 404, 'not_issued')
        self.err('/v1/find?q=' + urllib.request.quote(r['home'].rsplit(' ', 1)[0] + ' 10000'), 422, 'wrong_digits')
        self.err('/v1/find?q=hello', 404, 'not_found')

    def test_find_official_address(self):
        c = sqlite3.connect(self.s.db)
        rows = first_rows(3)
        for x in rows[1:]:
            c.execute("UPDATE codes SET official_address = 'Rue 4.101, Covè', official_key = ? WHERE machine = ?",
                      (X.norm_address('Rue 4.101, Covè'), x['machine']))
        c.commit()
        c.close()
        s, b = self.s.get('/v1/find?q=' + urllib.request.quote('rue 4.101,  cove'))
        self.assertEqual((s, b['kind'], b['count']), (200, 'official_address', 2), b)
        self.assertEqual(b['matches'][0]['display'], 'Rue 4.101, Covè')

    def test_at(self):
        r = self.row
        lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
        s, b = self.s.get('/v1/at?lat=%f&lng=%f' % (lat + 5 / 110574, lng))
        self.assertEqual((s, b['status'], b['code']['machine']), (200, 'found', r['machine']))
        self.assertEqual(b['distance_m'], 5)
        s, b = self.s.get('/v1/at?lat=7.2&lng=2.33')
        self.assertEqual((s, b['status']), (200, 'none'))
        self.assertEqual(b['area']['commune'], 'Covè')
        self.err('/v1/at?lat=48.85&lng=2.35', 404, 'outside_country')
        self.err('/v1/at?lat=x&lng=2', 400, 'bad_parameter')
        self.err('/v1/at?lat=7', 400, 'missing_parameter')

    def test_near(self):
        r = self.row
        s, b = self.s.get('/v1/near?lat=%s&lng=%s&radius=200&limit=3' % (r['entrance_lat'], r['entrance_lng']))
        self.assertEqual(s, 200)
        self.assertEqual(b['codes'][0]['code']['machine'], r['machine'])
        self.assertLessEqual(len(b['codes']), 3)
        ds = [c['distance_m'] for c in b['codes']]
        self.assertEqual(ds, sorted(ds))
        self.err('/v1/near?lat=7.2&lng=2.3&radius=501', 400, 'bad_parameter')
        self.err('/v1/near?lat=7.2&lng=2.3&limit=101', 400, 'bad_parameter')

    def test_verify(self):
        m = self.row['machine']
        s, b = self.s.get('/v1/verify?code=' + m)
        self.assertEqual((b['valid'], b['check_digit'], b['issued'], b['status']), (True, 'ok', True, 'provisional'))
        s, b = self.s.get('/v1/verify?code=' + m[:-1] + str((int(m[-1]) + 1) % 10))
        self.assertEqual((s, b['valid'], b['syntax'], b['check_digit']), (200, False, True, 'wrong'))
        s, b = self.s.get('/v1/verify?code=BJ-COV-04-001-1199')
        self.assertEqual((b['valid'], b['issued'], b['check_digit']), (False, False, 'missing'))
        s, b = self.s.get('/v1/verify?code=hello')
        self.assertEqual((b['valid'], b['syntax']), (False, False))
        self.err('/v1/verify', 400, 'missing_parameter')

    def test_spot(self):
        r = self.row
        s, b = self.s.get('/v1/spot?lat=%s&lng=%s' % (r['entrance_lat'], r['entrance_lng']))
        self.assertEqual((s, b['spot_code']), (200, r['spot_code']))
        s, b2 = self.s.get('/v1/spot/decode?code=' + urllib.request.quote(r['spot_code']))
        self.assertEqual(b2['spot_code'], r['spot_code'])
        self.assertLess(X.ground_m(b2['centre']['lat'], b2['centre']['lng'], float(r['entrance_lat']), float(r['entrance_lng'])), 2.2)
        s, b3 = self.s.get('/v1/spot/decode?code=' + b['machine'])
        self.assertEqual(b3['spot_code'], r['spot_code'])
        self.err('/v1/spot/decode?code=COV%2004%20%C2%B7%2034F', 400, 'invalid_spot')
        self.err('/v1/spot?lat=0&lng=0', 404, 'outside_country')
        # in no outline and west of every frame: the nearest cell of Atchannou's frame (SPEC 2.4);
        # decoding keeps the arrondissement the code names
        s, b = self.s.get('/v1/spot?lat=6.5089835&lng=1.6966827')
        self.assertEqual((s, b['spot_code'], b['machine']), (200, 'ATH 01 · C22 2W2', 'BJ-ATH-01-S-C222W2'))
        s, b = self.s.get('/v1/spot/decode?code=' + urllib.request.quote('ATH 01 · C22 2W2'))
        self.assertEqual((s, b['spot_code'], b['arrondissement']), (200, 'ATH 01 · C22 2W2', 'Atchannou'))

    def test_zones_and_areas(self):
        s, b = self.s.get('/v1/zones')
        self.assertEqual((s, b['count']), (200, 77))
        cov = [z for z in b['zones'] if z['key'] == 'COV'][0]
        self.assertEqual(cov['codes'], 5903)
        s, b = self.s.get('/v1/zones/cov')
        self.assertEqual(sum(a['codes'] for a in b['areas']), 5903)
        self.err('/v1/zones/ZZZ', 404, 'unknown_zone')
        s, b = self.s.get('/v1/areas/COV-04-001')
        self.assertEqual((s, b['plate_name'], b['codes']['total']), (200, 'Abayahoué', 3))
        s, b2 = self.s.get('/v1/areas/%d' % b['id'])
        self.assertEqual(b2['zone'], 'COV-04-001')
        s, b = self.s.get('/v1/areas?name=ABAYAHOUE')
        self.assertEqual([a['zone'] for a in b['areas']], ['COV-04-001'])
        s, b = self.s.get('/v1/areas?name=Attogon')
        self.assertGreater(b['count'], 1)
        self.err('/v1/areas/COV-99-999', 404, 'unknown_area')
        self.err('/v1/areas?name=Nowhereville', 404, 'unknown_name')

    def test_zone_paging(self):
        seen, after = [], ''
        while True:
            s, b = self.s.get('/v1/zones/COV/codes?limit=1000&after=' + after)
            self.assertEqual(s, 200)
            seen += [c['machine'] for c in b['codes']]
            if not b['next']:
                break
            after = b['next']
        self.assertEqual(len(seen), 5903)
        self.assertEqual(seen, sorted(seen))
        self.err('/v1/zones/COV/codes?limit=1001', 400, 'bad_parameter')

    def test_http_errors_and_cors(self):
        self.err('/v1/nothing', 404, 'no_such_endpoint')
        s, b, _ = self.s.call('DELETE', '/v1/codes/BJ-COV-04-001-1000-3')
        self.assertEqual((s, b['error']['code']), (405, 'method_not_allowed'))
        s, b, h = self.s.call('GET', '/v1/health', key=None, headers={'Origin': 'https://example.org'})
        self.assertEqual(h.get('Access-Control-Allow-Origin'), '*')

    def test_numbers_that_are_not_numbers(self):
        for path in ('/v1/zones/COV/codes?limit=nan', '/v1/zones/COV/codes?limit=inf', '/v1/zones/COV/codes?limit=2.5',
                     '/v1/near?lat=7.2&lng=2.33&limit=nan', '/v1/near?lat=7.2&lng=2.33&radius=inf',
                     '/v1/find?q=Rue%20nowhere&limit=nan', '/v1/at?lat=nan&lng=2.33'):
            self.err(path, 400, 'bad_parameter')


# ---------------------------------------------------------------------- issuing

class Issue(unittest.TestCase):
    def setUp(self):
        self.s = Served()

    def tearDown(self):
        self.s.close()

    def post(self, body, key=KEY):
        s, b, _ = self.s.call('POST', '/v1/codes', body, key=key)
        return s, b

    def test_keys_and_read_only(self):
        self.assertEqual(self.post({'lat': 7.2, 'lng': 2.33}, key=None)[1]['error']['code'], 'unauthorized')
        self.assertEqual(self.post({'lat': 7.2, 'lng': 2.33}, key='wrong')[0], 401)
        ro = Served(keys=())
        try:
            s, b, _ = ro.call('POST', '/v1/codes', {'lat': 7.2, 'lng': 2.33})
            self.assertEqual((s, b['error']['code']), (403, 'read_only'))
        finally:
            ro.close()

    def test_new_home_then_duplicates(self):
        s, b = self.post({'lat': 7.2, 'lng': 2.33})
        self.assertEqual(s, 201, b)
        self.assertEqual((b['status'], b['registry']['issued'], b['entrance']['kind']), ('provisional', 'on-demand', 'centre'))
        s, b2 = self.post({'lat': 7.2 + 1 / 110574, 'lng': 2.33})
        self.assertEqual((s, b2['error']['code'], b2['error']['machine']), (409, 'exists', b['machine']))
        ring = [[2.33100, 7.20100], [2.33122, 7.20100], [2.33122, 7.20112], [2.33100, 7.20112], [2.33100, 7.20100]]
        s, b3 = self.post({'lat': 7.20106, 'lng': 2.33111, 'outline': ring})
        self.assertEqual(s, 201, b3)
        self.assertEqual((b3['profile']['structures'], b3['profile']['class']), (1, 'residential'))
        shifted = [[x + 0.00010, y] for x, y in ring]  # shares 55 % of the first outline
        s, b4 = self.post({'lat': 7.20106, 'lng': 2.33128, 'outline': shifted})
        self.assertEqual((s, b4['error']['code']), (409, 'exists'))
        s, b5 = self.post({'lat': 7.203, 'lng': 2.333, 'outline': [[2.333, 7.203], [2.33301, 7.203], [2.33301, 7.20301]]})
        self.assertEqual((s, b5['error']['code']), (422, 'bad_outline'))

    def test_request_errors(self):
        self.assertEqual(self.post({'lat': 48.85, 'lng': 2.35})[1]['error']['code'], 'outside_country')
        self.assertEqual(self.post({'lat': 'x', 'lng': 2.35})[1]['error']['code'], 'bad_parameter')
        r = first_rows(1)[0]
        far = self.post({'lat': float(r['entrance_lat']) + 0.002, 'lng': float(r['entrance_lng']), 'of': r['machine']})
        self.assertEqual((far[0], far[1]['error']['code']), (422, 'too_far'))
        self.assertEqual(self.post({'lat': 7.2, 'lng': 2.33, 'of': 'BJ-COV-04-001-1199-0'})[1]['error']['code'], 'not_issued')
        s, b, _ = self.s.call('POST', '/v1/codes', None)
        self.assertEqual(s, 400)
        bools = self.post({'lat': 7.2, 'lng': 2.33, 'outline': [[True, False], [2.33, 7.2], [2.331, 7.2]]})
        self.assertEqual((bools[0], bools[1]['error']['code']), (400, 'bad_body'))
        s, b, _ = self.s.call('POST', '/v1/codes', None, headers={'Content-Length': 'abc'})
        self.assertEqual((s, b['error']['code']), (400, 'bad_body'))

    def test_daily_limit(self):
        lim = Served(per_day=2)
        try:
            for i in range(2):
                s, b, _ = lim.call('POST', '/v1/codes', {'lat': 7.19 + i * 0.001, 'lng': 2.32})
                self.assertEqual(s, 201, b)
            s, b, _ = lim.call('POST', '/v1/codes', {'lat': 7.195, 'lng': 2.32})
            self.assertEqual((s, b['error']['code']), (429, 'rate_limited'))
        finally:
            lim.close()

    def test_doors_match_the_issuer_and_extension_blocks_persist(self):
        parity = read_json(PARITY)
        for sc in parity['scenarios']:
            if not sc.get('doors'):
                continue
            for d, want in zip(sc['doors'], sc['want']):
                s, b = self.post(d)
                self.assertEqual(s, 201, (sc['name'], b))
                self.assertEqual((b['machine'], b['home'], b['written'], b['entrance']['kind']),
                                 (want['machine'], want['home'], want['written'], 'door'), sc['name'])
            s, a = self.s.get('/v1/areas/' + sc['zone'])
            self.assertEqual(a['blocks'], sc['want'][-1]['blocks'])
            # a code in the new block is found by its remembered form
            last = sc['want'][-1]
            s, f = self.s.get('/v1/find?q=' + urllib.request.quote(last['written']))
            self.assertEqual(f['matches'][0]['machine'], last['machine'])
        # the export carries the new codes and blocks, and imports again
        out = os.path.join(self.s.dir, 'out')
        store.export_registry(self.s.db, out, log=quiet)
        man = read_json(os.path.join(out, 'MANIFEST.json'))
        added = sum(len(sc.get('doors') or []) for sc in parity['scenarios'])
        self.assertEqual(man['codes'], 5903 + added)
        for f, h in man['sha256'].items():
            self.assertEqual(hashlib.sha256(unzip(os.path.join(out, f + '.gz'))).hexdigest(), h)
        db2 = os.path.join(self.s.dir, 'again.sqlite')
        self.assertEqual(store.import_registry(db2, out, log=quiet), 5903 + added)
        c2 = store.connect(db2)
        reg = store.load_areas(c2)
        c2.close()
        for sc in parity['scenarios']:
            if sc.get('doors'):
                self.assertEqual(reg.by_zone[sc['zone']].blocks, sc['want'][-1]['blocks'])

    def test_patch_status_and_entrance(self):
        r = first_rows(1)[0]
        m = r['machine']
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + m, {'status': 'confirmed'})
        self.assertEqual((s, b['status']), (200, 'confirmed'))
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + m, {'entrance': {'lat': float(r['entrance_lat']) + 0.0002,
                                                                       'lng': float(r['entrance_lng'])}})
        self.assertEqual((s, b['entrance']['kind']), (200, 'gate'))
        self.assertNotEqual(b['spot_code'], r['spot_code'])
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + m, {'entrance': {'lat': float(r['entrance_lat']) + 0.002,
                                                                       'lng': float(r['entrance_lng'])}})
        self.assertEqual((s, b['error']['code']), (422, 'too_far'))
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + m, {'status': 'retired'})
        self.assertEqual(b['status'], 'retired')
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + m, {'status': 'provisional'})
        self.assertEqual((s, b['error']['code']), (409, 'retired'))
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + m, {'status': 'gone'})
        self.assertEqual(b['error']['code'], 'bad_body')
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + m, {'status': 'confirmed'}, key=None)
        self.assertEqual(s, 401)
        # a retired code is never found by point, and its number is never given again
        s, at = self.s.get('/v1/at?lat=%s&lng=%s' % (r['entrance_lat'], r['entrance_lng']))
        self.assertNotEqual(at.get('code', {}).get('machine'), m)
        s, f = self.s.get('/v1/find?q=' + urllib.request.quote(r['home']))
        self.assertEqual(f['error']['code'], 'retired')
        s, b = self.post({'lat': float(r['entrance_lat']), 'lng': float(r['entrance_lng']), 'of': m})
        self.assertEqual(s, 201, b)
        self.assertNotEqual(b['number'], int(r['number']))



# ---------------------------------------------------------------------- points in no outline

def with_gaps(d):
    """The fixture plus server/testdata/gaps.csv: 30 published compounds of Athiémé,
    Karimama and Ouaké whose entrances lie in no arrondissement outline, as the
    unit files of a registry with its manifest."""
    reg = os.path.join(d, 'registry')
    shutil.copytree(FIXTURE, reg)
    with open(GAPS, encoding='utf-8', newline='') as fh:
        header, lines = fh.readline(), fh.readlines()
    man = read_json(os.path.join(reg, 'MANIFEST.json'))
    for unit in sorted({ln.split(',', 1)[0].split('-')[1] for ln in lines}):
        body = (header + ''.join(ln for ln in lines if ln.split('-')[1] == unit)).encode('utf-8')
        with gzip.open(os.path.join(reg, unit + '.csv.gz'), 'wb') as fh:
            fh.write(body)
        man['byUnit'][unit] = body.count(b'\n') - 1
        man['sha256'][unit + '.csv'] = hashlib.sha256(body).hexdigest()
    man['codes'] = sum(man['byUnit'].values())
    write_json(os.path.join(reg, 'MANIFEST.json'), man)
    return reg


class Gaps(unittest.TestCase):
    """A point in no arrondissement outline is in Benin when SPEC 2.4 gives it a spot
    code, as the N-Ways issuer decides: it is found by point and can be issued."""

    FREE = (12.2855163, 2.9631812)       # 43 m east of BJ-KAR-05-008-1008-8, in no outline, no code
    OUTSIDE = [(9.5, 0.9), (12.6, 3.0), (48.85, 2.35)]   # a neighbouring country twice, then Paris: no spot code

    def setUp(self):
        self.s = Served(registry=with_gaps)
        import csv
        with open(GAPS, encoding='utf-8', newline='') as fh:
            self.rows = list(csv.DictReader(fh))

    def tearDown(self):
        self.s.close()

    def test_fixture_lies_in_no_outline(self):
        self.assertGreaterEqual(len(self.rows), 20)
        self.assertEqual({r['zone'][:3] for r in self.rows}, {'ATH', 'KAR', 'OUA'})
        for r in self.rows + [{'entrance_lat': self.FREE[0], 'entrance_lng': self.FREE[1]}]:
            lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
            self.assertIsNone(X.E.arrondissement_at(lat, lng))
            self.assertTrue(X.in_country(lat, lng))
        for lat, lng in self.OUTSIDE:
            self.assertFalse(X.in_country(lat, lng))

    def test_at_finds_every_compound_in_a_gap(self):
        for r in self.rows:
            s, b = self.s.get('/v1/at?lat=%s&lng=%s' % (r['entrance_lat'], r['entrance_lng']))
            self.assertEqual((s, b['status'], b['code']['machine'], b['distance_m']), (200, 'found', r['machine'], 0), r)
            self.assertEqual(b['code']['spot_code'], r['spot_code'])
            self.assertEqual(b['area']['zone'], r['zone'])

    def test_issue_in_a_gap_and_refuse_outside(self):
        lat, lng = self.FREE
        s, b = self.s.get('/v1/at?lat=%s&lng=%s' % (lat, lng))
        self.assertEqual((s, b['status'], b['can_issue'], b['area']['zone']), (200, 'none', True, 'KAR-05-008'))
        s, c, _ = self.s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng})
        self.assertEqual(s, 201, c)
        self.assertEqual((c['zone'], c['status'], c['registry']['issued']), ('KAR-05-008', 'provisional', 'on-demand'))
        self.assertTrue(c['spot_code'].startswith('KAR 05 · '), c['spot_code'])
        s, b = self.s.get('/v1/at?lat=%s&lng=%s' % (lat, lng))
        self.assertEqual((b['status'], b['code']['machine']), ('found', c['machine']))
        s, d, _ = self.s.call('POST', '/v1/codes', {'lat': lat + 0.0001, 'lng': lng, 'of': c['machine']})
        self.assertEqual((s, d['zone'], d['entrance']['kind']), (201, 'KAR-05-008', 'door'))
        for lat, lng in self.OUTSIDE:
            s, b = self.s.get('/v1/at?lat=%s&lng=%s' % (lat, lng))
            self.assertEqual((s, b['error']['code']), (404, 'outside_country'))
            s, b, _ = self.s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng})
            self.assertEqual((s, b['error']['code']), (422, 'outside_country'))



class Border(unittest.TestCase):
    """The border decides (engine/SPEC.md 1b): no code more than 300 m outside Benin's
    national border, whatever arrondissement outline or spot frame holds the point."""

    ACROSS = [(6.42, 2.76),     # about 6 km across the south-eastern border, in a spot frame's reach
              (8.32, 1.62),     # 1.6 km across the western border, inside an arrondissement outline
              (6.45, 2.7102)]   # 393 m across, inside an arrondissement outline
    INSIDE = (6.45, 2.70)       # inside the border, near it
    NEAR = (6.45, 2.708)        # 150 m outside the border: within 300 m, so in Benin
    EDGE = (6.45, 2.7088)       # about 240 m outside; 77 m further east is 316 m outside

    def setUp(self):
        self.s = Served()

    def tearDown(self):
        self.s.close()

    def test_shipped_border(self):
        path = os.path.join(REPO, 'engine', 'data', 'border.json')
        self.assertLess(os.path.getsize(path), 1 << 20)
        d = read_json(path)
        self.assertEqual((d['toleranceM'], d['borderM']), (50.0, 300.0))
        self.assertLessEqual(max(d['measuredM'].values()), d['toleranceM'])

    def test_zones_reach_over_the_border_but_do_not_decide(self):
        for lat, lng in self.ACROSS:
            self.assertIsNotNone(X.E.spot_arrondissement(lat, lng))
            self.assertTrue(X.abroad(lat, lng))
            self.assertFalse(X.in_country(lat, lng))
        self.assertIsNotNone(X.E.arrondissement_at(*self.ACROSS[1]))
        self.assertIsNotNone(X.E.arrondissement_at(*self.ACROSS[2]))
        for lat, lng in (self.INSIDE, self.NEAR, self.EDGE):
            self.assertFalse(X.abroad(lat, lng))
            self.assertTrue(X.in_country(lat, lng))

    def test_issue_across_the_border_is_refused(self):
        for lat, lng in self.ACROSS:
            s, b, _ = self.s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng})
            self.assertEqual((s, b['error']['code']), (422, 'outside_country'), (lat, lng))
            s, b = self.s.get('/v1/at?lat=%s&lng=%s' % (lat, lng))
            self.assertEqual((s, b['error']['code']), (404, 'outside_country'))

    def test_issue_inside_and_near_the_border_is_accepted(self):
        for lat, lng in (self.INSIDE, self.NEAR):
            s, c, _ = self.s.call('POST', '/v1/codes', {'lat': lat, 'lng': lng})
            self.assertEqual(s, 201, c)
            self.assertEqual(c['registry']['issued'], 'on-demand')

    def test_entrance_never_moves_across_the_border(self):
        s, c, _ = self.s.call('POST', '/v1/codes', {'lat': self.EDGE[0], 'lng': self.EDGE[1]})
        self.assertEqual(s, 201, c)
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + c['machine'], {'entrance': {'lat': 6.45, 'lng': 2.7095}})
        self.assertEqual((s, b['error']['code']), (422, 'outside_country'))
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + c['machine'], {'entrance': {'lat': 6.45, 'lng': 2.7085}})
        self.assertEqual(s, 200, b)


if __name__ == '__main__':
    unittest.main()
