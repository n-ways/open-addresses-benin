"""The JSON API (/v1). Every response is JSON; every error is
{"error": {"code": "...", "message": "..."}} with the matching HTTP status."""
import hashlib
import json
import re
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from . import COUNTRY, COUNTRY_NAME, CREDIT, CREDIT_URL, LICENCES, SPEC
from . import engine as X
from . import store as S
from .engine import CodeError

MAX_BODY = 64 * 1024
MAX_OUTLINE = 500
PAGE_DEFAULT, PAGE_MAX = 100, 1000
NEAR_DEFAULT_M, NEAR_DEFAULT_LIMIT = 100.0, 20
FIND_DEFAULT, FIND_MAX = 20, 100


class Config(object):
    def __init__(self, db, keys=(), per_day=5, cors=()):
        self.db = db
        self.keys = {k.strip(): hashlib.sha256(k.strip().encode()).hexdigest()[:16] for k in keys if k.strip()}
        self.per_day = per_day
        self.cors = [c.strip() for c in cors if c.strip()]


class App(object):
    def __init__(self, config):
        self.config = config
        self.store = S.Store(config.db)
        self._stats = None
        self._stats_lock = threading.Lock()

    # ---------------------------------------------------------------- shared pieces

    def stats(self):
        """Counts by status, by commune and by area (cached; reset by every write)."""
        with self._stats_lock:
            if self._stats is None:
                c = self.store.conn()
                st = {r[0]: r[1] for r in c.execute('SELECT status, count(*) FROM codes GROUP BY status')}
                units = {r[0]: r[1] for r in c.execute('SELECT unit, count(*) FROM codes GROUP BY unit')}
                zones = {r[0]: r[1] for r in c.execute('SELECT zone, count(*) FROM codes GROUP BY zone')}
                self._stats = {'status': st, 'units': units, 'zones': zones, 'total': sum(st.values())}
            return self._stats

    def forget_stats(self):
        with self._stats_lock:
            self._stats = None

    def area_brief(self, a):
        if a is None:
            return None
        return {'zone': a.zone, 'id': a.id, 'plate_name': a.plate, 'official_name': a.official,
                'provisional_name': a.provisional, 'commune_key': a.unit, 'commune': a.commune,
                'arrondissement': a.arrondissement, 'departement': a.departement}

    def card(self, r):
        a = self.store.register.by_zone.get(r['zone'])
        n = int(r['number'])
        lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
        plate = a.plate if a else r['home'].rsplit(' ', 1)[0]
        nullable = lambda v: v if v != '' else None  # noqa: E731
        return {
            'machine': r['machine'],
            'home': r['home'],
            'written': r['written'],
            'spoken': '%s, %s' % (plate, X.E.spoken_number(n)),
            'display': r['official_address'] or r['written'],
            'zone': r['zone'],
            'number': n,
            'check': int(r['check']),
            'status': r['status'],
            'issued': r['issued'],
            'issued_at': r['issued_at'],
            'entrance': {'lat': lat, 'lng': lng, 'kind': r['entrance_kind']},
            'spot_code': r['spot_code'],
            'plus_code': X.plus_code(lat, lng),
            'official_address': nullable(r['official_address']),
            'official_name': r['official_name'],
            'area': self.area_brief(a),
            'profile': {'class': nullable(r['class']), 'use': nullable(r['use']), 'kind': nullable(r['kind']),
                        'structures': int(r['structures']), 'floor_area_m2': float(r['floor_area_m2']),
                        'rule': nullable(r['rule']), 'estate': nullable(r['estate'])},
            'registry': {c: r[c] for c in S.CODE_COLUMNS},
            'credit': CREDIT,
        }

    def place_for(self, lat, lng):
        """The area a new compound takes (SPEC 7): the area of the nearest issued code
        within 250 m, so a new house joins its neighbours; else the code area of the
        point; else the nearest area."""
        reg = self.store.register
        hit = self.store.code_at(lat, lng, X.PLACE_NEAR_M)
        if hit:
            a = reg.by_zone.get(hit[1]['zone'])
            if a is not None:
                return a
        a = reg.area_at(lat, lng)
        if a is not None and a.blocks:
            return a
        return reg.nearest_area(lat, lng)

    # ---------------------------------------------------------------- reads

    def health(self, req):
        return 200, {'status': 'ok', 'country': COUNTRY, 'codes': self.stats()['total'],
                     'registry_exported': self.store.manifest.get('exported')}

    def info(self, req):
        st = self.stats()
        c = self.store.conn()
        return 200, {
            'country': COUNTRY, 'name': COUNTRY_NAME,
            'codes': {'total': st['total'], 'by_status': st['status']},
            'zones': len(st['units']), 'areas': len(self.store.register.areas),
            'zone_kind': 'commune', 'area_kind': 'quartier or village',
            'registry': {'exported': self.store.manifest.get('exported'), 'imported_at': S.meta(c, 'imported_at'),
                         'codes': self.store.manifest.get('codes'), 'local_changes': S.meta(c, 'dirty') == '1'},
            'issuing': {'enabled': bool(self.config.keys), 'per_key_per_day': self.config.per_day},
            'engine': S.ENGINE, 'spec': SPEC, 'spatial_index': S.meta(c, 'spatial'),
            'licences': LICENCES, 'credit': CREDIT, 'credit_url': CREDIT_URL,
        }

    def code(self, req, machine):
        p = X.parse_machine(unquote(machine))
        r = self.store.by_machine(p['canonical'])
        if r is None:
            raise CodeError('not_issued', '%s is a valid code shape but no home has it.' % p['canonical'], 404)
        return 200, self.card(r)

    def find(self, req):
        text = req.param('q', required=True)
        if X.looks_spot(text):
            lat, lng = X.spot_decode(text)
            hit = self.store.code_at(lat, lng, X.SPOT_FOUND_M)
            if not hit:
                raise CodeError('no_code_at_spot', 'The spot %s is not on a home.' % text.strip(), 404)
            return 200, {'query': text, 'kind': 'spot', 'count': 1, 'more': False, 'matches': [self.card(hit[1])]}
        if X.looks_machine(text):
            p = X.parse_machine(text)
            r = self.store.by_machine(p['canonical'])
            if r is None:
                raise CodeError('not_issued', '%s is a valid code shape but no home has it.' % p['canonical'], 404)
            return 200, {'query': text, 'kind': 'machine', 'count': 1, 'more': False, 'matches': [self.card(r)]}
        first_error = None
        try:
            a, n = X.resolve_remembered(self.store.register, text)
            r = self.store.by_number(a.name_index, n)
            if r is None or r['zone'] != a.zone:
                raise CodeError('not_issued', 'No home has %s · %s yet (the number is in the range of %s, %s).'
                                % (a.plate, X.E.spoken_number(n), a.plate, a.commune), 404)
            if r['status'] == 'retired':
                raise CodeError('retired', '%s was retired: there is no home there any more.' % r['written'], 404)
            return 200, {'query': text, 'kind': 'remembered', 'count': 1, 'more': False, 'matches': [self.card(r)]}
        except CodeError as e:
            if e.code not in ('invalid_code', 'unknown_name'):
                raise
            first_error = e
        limit = req.integer('limit', FIND_DEFAULT)
        if not 0 < limit <= FIND_MAX:
            raise CodeError('bad_parameter', 'limit is at most %d.' % FIND_MAX)
        n, rows = self.store.by_official(X.norm_address(text), limit)
        if n:
            return 200, {'query': text, 'kind': 'official_address', 'count': n, 'more': n > len(rows),
                         'matches': [self.card(r) for r in rows]}
        if first_error.code == 'unknown_name':
            raise first_error
        raise CodeError('not_found', 'Nothing matches "%s": expected a remembered code ("Cadjéhoun 18 07"), a machine '
                        'code, an official address or a spot code.' % text.strip(), 404)

    def at(self, req):
        lat, lng = req.point()
        if not X.in_country(lat, lng):
            raise CodeError('outside_country', 'That point is outside Benin.', 404)
        area = self.area_brief(self.place_for(lat, lng))
        hit = self.store.code_at(lat, lng, X.FOUND_M)
        if hit:
            return 200, {'status': 'found', 'distance_m': round(hit[0]), 'code': self.card(hit[1]), 'area': area}
        return 200, {'status': 'none', 'can_issue': bool(self.config.keys), 'area': area}

    def near(self, req):
        lat, lng = req.point()
        radius = req.number('radius', NEAR_DEFAULT_M)
        limit = req.integer('limit', NEAR_DEFAULT_LIMIT)
        if not 0 < radius <= X.NEAR_MAX_M:
            raise CodeError('bad_parameter', 'radius is in metres, at most %d.' % X.NEAR_MAX_M)
        if not 0 < limit <= X.NEAR_MAX_RESULTS:
            raise CodeError('bad_parameter', 'limit is at most %d.' % X.NEAR_MAX_RESULTS)
        hits = self.store.within(lat, lng, radius)
        return 200, {'lat': lat, 'lng': lng, 'radius_m': radius, 'count': min(len(hits), limit), 'more': len(hits) > limit,
                     'codes': [{'distance_m': round(d, 1), 'code': self.card(r)} for d, r in hits[:limit]]}

    def verify(self, req):
        text = req.param('code', required=True)
        out = {'code': text, 'valid': False, 'syntax': False, 'check_digit': None, 'issued': False, 'status': None,
               'machine': None, 'zone': None, 'reason': None}
        if not X.looks_machine(text):
            out['reason'] = 'Not an N-Ways Benin machine code: expected BJ-CCC-AA-QQQ-NNNN-K.'
            return 200, out
        out['syntax'] = True
        try:
            p = X.parse_machine(text)
        except CodeError as e:
            out['reason'] = e.message
            if e.code == 'check_digit':
                out['check_digit'] = 'wrong'
            return 200, out
        out.update(machine=p['canonical'], zone=p['zone'], check_digit='ok' if p['hasCheck'] else 'missing')
        r = self.store.by_machine(p['canonical'])
        if r is None:
            out['reason'] = 'The code is well formed but no home has it.'
            return 200, out
        out.update(issued=True, status=r['status'], valid=p['hasCheck'] and r['status'] != 'retired')
        if not p['hasCheck']:
            out['reason'] = 'The check digit is missing: the full code is %s.' % p['canonical']
        elif r['status'] == 'retired':
            out['reason'] = 'The code was retired; it is never given to another home.'
        return 200, out

    def spot(self, req):
        lat, lng = req.point()
        try:
            s = X.spot(lat, lng)
        except ValueError:
            raise CodeError('outside_country', 'That point is outside Benin.', 404)
        clat, clng = X.spot_decode(s['display'])
        return 200, {'spot_code': s['display'], 'machine': s['machine'], 'commune': s['commune'],
                     'arrondissement': s['arrondissement'], 'cell_m': X.E.CELL_M,
                     'centre': {'lat': round(clat, 7), 'lng': round(clng, 7)}}

    def spot_decode(self, req):
        text = req.param('code', required=True)
        s, lat, lng = X.spot_of_code(text)
        return 200, {'spot_code': s['display'], 'machine': s['machine'], 'commune': s['commune'],
                     'arrondissement': s['arrondissement'], 'cell_m': X.E.CELL_M,
                     'centre': {'lat': round(lat, 7), 'lng': round(lng, 7)}}

    def zones(self, req):
        st = self.stats()
        out = []
        by_unit = {}
        for a in self.store.register.areas:
            by_unit.setdefault(a.unit, []).append(a)
        for k in sorted(by_unit):
            a = by_unit[k][0]
            out.append({'key': k, 'name': a.commune, 'departement': a.departement, 'areas': len(by_unit[k]),
                        'codes': st['units'].get(k, 0), 'file': '%s.csv.gz' % k})
        return 200, {'count': len(out), 'zones': out}

    def zone(self, req, key):
        key = key.upper()
        areas = [a for a in self.store.register.areas if a.unit == key]
        if not areas:
            raise CodeError('unknown_zone', 'There is no commune with key %s.' % key, 404)
        st = self.stats()
        return 200, {'key': key, 'name': areas[0].commune, 'departement': areas[0].departement,
                     'codes': st['units'].get(key, 0), 'file': '%s.csv.gz' % key,
                     'areas': [dict(self.area_brief(a), blocks=a.blocks, codes=st['zones'].get(a.zone, 0))
                               for a in sorted(areas, key=lambda a: a.zone)]}

    def zone_codes(self, req, key):
        key = key.upper()
        if not any(a.unit == key for a in self.store.register.areas):
            raise CodeError('unknown_zone', 'There is no commune with key %s.' % key, 404)
        after = req.param('after') or ''
        limit = req.integer('limit', PAGE_DEFAULT)
        if not 0 < limit <= PAGE_MAX:
            raise CodeError('bad_parameter', 'limit is at most %d.' % PAGE_MAX)
        rows = self.store.zone_page(key, after, limit + 1)
        more = len(rows) > limit
        rows = rows[:limit]
        return 200, {'zone': key, 'count': len(rows), 'codes': [self.card(r) for r in rows],
                     'next': rows[-1]['machine'] if more else None}

    def area_detail(self, a):
        st = self.stats()
        c = self.store.conn()
        by = {r[0]: r[1] for r in c.execute('SELECT status, count(*) FROM codes WHERE zone = ? GROUP BY status', (a.zone,))}
        lo_hi = c.execute('SELECT min(num), max(num) FROM codes WHERE zone = ?', (a.zone,)).fetchone()
        fam = self.store.register.families.get(a.name_key, [])
        return dict(self.area_brief(a), name_key=a.name_key, name_index=a.name_index, digits=a.digits, blocks=a.blocks,
                    place=({'lat': a.point[0], 'lng': a.point[1]} if a.point else None),
                    frame=list(a.frame) if any(a.frame) else None,
                    codes={'total': st['zones'].get(a.zone, 0), 'by_status': by},
                    numbers={'lowest': lo_hi[0], 'highest': lo_hi[1]},
                    same_name=[x.zone for x in fam if x.zone != a.zone])

    def area(self, req, ident):
        reg = self.store.register
        a = reg.by_id.get(int(ident)) if ident.isdigit() else reg.by_zone.get(ident.upper())
        if a is None:
            raise CodeError('unknown_area', 'There is no code area %s.' % ident, 404)
        return 200, self.area_detail(a)

    def areas(self, req):
        name = req.param('name', required=True)
        k = X.norm_name(name)
        alias = X.E.names()['_alias'].get(k)
        out = [a for a in self.store.register.areas if a.name_key == k or X.norm_name(a.official) == k
               or (alias and a.name_key == alias)]
        if not out:
            raise CodeError('unknown_name', 'No code area of Benin is called "%s".' % name.strip(), 404)
        out.sort(key=lambda a: a.zone)
        return 200, {'name': name, 'count': len(out), 'areas': [self.area_detail(a) for a in out]}

    # ---------------------------------------------------------------- writes

    def key_id(self, req):
        if not self.config.keys:
            raise CodeError('read_only', 'This deployment does not issue codes: it serves the published registry only.', 403)
        h = req.headers.get('Authorization', '')
        m = re.match(r'^Bearer\s+(\S+)\s*$', h)
        if not m or m.group(1) not in self.config.keys:
            raise CodeError('unauthorized', 'A valid issuing key is required (Authorization: Bearer <key>).', 401)
        return self.config.keys[m.group(1)]

    def issue(self, req):
        kid = self.key_id(req)
        body = req.json()
        lat, lng = _latlng(body.get('lat'), body.get('lng'))
        of = body.get('of')
        outline = body.get('outline')
        if of is not None and not isinstance(of, str):
            raise CodeError('bad_body', '"of" is the machine code of the compound the door belongs to.')
        if outline is not None:
            if not isinstance(outline, list) or len(outline) > MAX_OUTLINE or \
                    not all(isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p) for p in outline):
                raise CodeError('bad_body', '"outline" is a list of at most %d [lng, lat] pairs.' % MAX_OUTLINE)
        st = self.store
        with st.write_lock:
            # Counted under the lock, so parallel requests on one key cannot pass the limit together.
            if st.issued_by(kid, time.time() - 86400) >= self.config.per_day:
                raise CodeError('rate_limited', 'This key has issued %d codes in the last 24 hours, its daily limit.'
                                % self.config.per_day, 429)
            reg = st.register
            if not X.in_country(lat, lng):
                raise CodeError('outside_country', 'That point is outside Benin, so it cannot have a Benin code.', 422)
            area_m2, ring = 0.0, None
            if not of:
                hit = st.code_at(lat, lng, X.SAME_BUILDING_M)
                if hit:
                    raise _exists(hit[1])
                if outline and len(outline) >= 3:
                    ring = [[float(p[0]), float(p[1])] for p in outline]
                    if ring[0] == ring[-1]:
                        ring = ring[:-1]
                    area_m2 = X.ring_area_m2(ring)
                    if len(ring) < 3 or area_m2 < X.MIN_AREA_M2 or area_m2 > X.MAX_AREA_M2:
                        raise CodeError('bad_outline', "That outline is %.0f m², but a home's is between 6 m² and 2 ha." % area_m2, 422)
                    other = st.overlapping(ring)
                    if other is not None:
                        raise _exists(other)
            if of:
                o = st.by_machine(of.strip())
                if o is None:
                    raise CodeError('not_issued', 'There is no code %s to add a door to.' % of, 404)
                if X.plane_m(float(o['entrance_lat']), float(o['entrance_lng']), lat, lng) > X.DOOR_MAX_M:
                    raise CodeError('too_far', 'That door is more than 80 m from %s.' % o['written'], 422)
                a = reg.by_zone.get(o['zone'])
            else:
                a = self.place_for(lat, lng)
            if a is None:
                raise CodeError('no_area', 'There is no code area for this point.', 422)
            work = a.copy()
            nb = len(work.blocks)
            num = reg.insert(work, st.zone_numbers(a.zone), lat, lng)
            if num is None:
                raise CodeError('area_full', '%s has used every number of its name; the commune chooses a qualifier '
                                'before more homes there get a code.' % a.plate, 409)
            new_blocks = [list(b) for b in work.blocks[nb:]]
            f = reg.forms(work, num)
            floor = round(round(area_m2 * 10) / 10 * 10) / 10 if area_m2 > 0 else 0.0
            row = {'machine': f['machine'], 'home': f['home'], 'written': f['written'], 'zone': a.zone,
                   'official_name': a.official, 'number': str(num), 'check': str(f['check']), 'status': 'provisional',
                   'issued': 'on-demand', 'issued_at': S.now_rfc3339(), 'entrance_lat': '%.7f' % lat,
                   'entrance_lng': '%.7f' % lng, 'entrance_kind': 'door' if of else 'centre',
                   'spot_code': X.spot_display(lat, lng), 'official_address': '',
                   'class': 'residential' if area_m2 > 0 else '', 'use': 'residential', 'kind': 'door' if of else 'building',
                   'structures': '1' if area_m2 > 0 else '0', 'floor_area_m2': '%.1f' % floor, 'rule': '', 'estate': ''}
            st.insert_local(row, a.unit, (lat, lng), json.dumps(ring) if ring else None, new_blocks, kid)
            self.forget_stats()
            return 201, self.card(st.by_machine(f['machine']))

    def patch(self, req, machine):
        kid = self.key_id(req)
        body = req.json()
        p = X.parse_machine(unquote(machine))
        st = self.store
        with st.write_lock:
            r = st.by_machine(p['canonical'])
            if r is None:
                raise CodeError('not_issued', 'No home has the code %s.' % p['canonical'], 404)
            fields = {}
            status = body.get('status')
            if status is not None:
                if status not in ('provisional', 'confirmed', 'retired'):
                    raise CodeError('bad_body', '"status" is provisional, confirmed or retired.')
                if r['status'] == 'retired' and status != 'retired':
                    raise CodeError('retired', 'A retired code stays retired: its number is never used again.', 409)
                fields['status'] = status
            ent = body.get('entrance')
            if ent is not None:
                if not isinstance(ent, dict):
                    raise CodeError('bad_body', '"entrance" is {"lat": ..., "lng": ...}.')
                lat, lng = _latlng(ent.get('lat'), ent.get('lng'))
                if X.plane_m(float(r['entrance_lat']), float(r['entrance_lng']), lat, lng) > X.MOVE_MAX_M:
                    raise CodeError('too_far', 'An entrance moves at most 80 m.', 422)
                if r['status'] == 'retired':
                    raise CodeError('retired', 'A retired code has no entrance to move.', 409)
                if X.abroad(lat, lng):
                    raise CodeError('outside_country', 'That point is outside Benin, so it cannot be a Benin entrance.', 422)
                fields.update({'entrance_lat': '%.7f' % lat, 'entrance_lng': '%.7f' % lng, 'entrance_kind': 'gate',
                               'spot_code': X.spot_display(lat, lng), 'lat': float('%.7f' % lat),
                               'lng': float('%.7f' % lng), 'grid': S.grid_cell(lat, lng)})
            if not fields:
                raise CodeError('bad_body', 'Nothing to change: give "status" and/or "entrance".')
            r = st.update(p['canonical'], fields, kid)
            self.forget_stats()
            return 200, self.card(r)


def _exists(r):
    e = CodeError('exists', 'This building already has its code: %s.' % r['written'], 409)
    e.machine = r['machine']
    return e


def _latlng(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise CodeError('bad_parameter', 'lat and lng are decimal degrees (WGS 84).')
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or lat != lat or lng != lng:
        raise CodeError('bad_parameter', 'lat is between -90 and 90 and lng between -180 and 180.')
    return lat, lng


# -------------------------------------------------------------------- HTTP

ROUTES = [
    ('GET', r'/v1/health', 'health'),
    ('GET', r'/v1/info', 'info'),
    ('GET', r'/v1/find', 'find'),
    ('GET', r'/v1/at', 'at'),
    ('GET', r'/v1/near', 'near'),
    ('GET', r'/v1/verify', 'verify'),
    ('GET', r'/v1/spot', 'spot'),
    ('GET', r'/v1/spot/decode', 'spot_decode'),
    ('GET', r'/v1/zones', 'zones'),
    ('GET', r'/v1/zones/([^/]+)', 'zone'),
    ('GET', r'/v1/zones/([^/]+)/codes', 'zone_codes'),
    ('GET', r'/v1/areas', 'areas'),
    ('GET', r'/v1/areas/([^/]+)', 'area'),
    ('POST', r'/v1/codes', 'issue'),
    ('GET', r'/v1/codes/([^/]+)', 'code'),
    ('PATCH', r'/v1/codes/([^/]+)', 'patch'),
]
ROUTES = [(m, re.compile('^' + p + '$'), h) for m, p, h in ROUTES]


class Request(object):
    def __init__(self, handler, query):
        self.h = handler
        self.query = query
        self.headers = handler.headers

    def param(self, name, required=False):
        v = self.query.get(name)
        if v is None or v[0].strip() == '':
            if required:
                raise CodeError('missing_parameter', 'The "%s" parameter is required.' % name)
            return None
        return v[0]

    def number(self, name, default):
        v = self.param(name)
        if v is None:
            return default
        try:
            x = float(v)
        except ValueError:
            x = float('nan')
        if x != x or x in (float('inf'), float('-inf')):
            raise CodeError('bad_parameter', '"%s" must be a number.' % name)
        return x

    def integer(self, name, default):
        x = self.number(name, default)
        if x != int(x):
            raise CodeError('bad_parameter', '"%s" must be a whole number.' % name)
        return int(x)

    def point(self):
        return _latlng(self.param('lat', required=True), self.param('lng', required=True))

    def json(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            n = -1
        if n < 0:
            raise CodeError('bad_body', 'The Content-Length header is not a byte count.')
        if n > MAX_BODY:
            raise CodeError('body_too_large', 'The request body is over 64 KB.', 413)
        raw = self.h.rfile.read(n) if n else b''
        try:
            body = json.loads(raw.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            raise CodeError('bad_body', 'The request body is not valid JSON.')
        if not isinstance(body, dict):
            raise CodeError('bad_body', 'The request body is a JSON object.')
        return body


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'NWaysAddressing/1.0'
        sys_version = ''
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            sys.stderr.write('%s %s\n' % (self.log_date_time_string(), fmt % args))

        def _cors(self):
            origin = self.headers.get('Origin')
            allowed = app.config.cors
            if origin and ('*' in allowed or origin in allowed):
                self.send_header('Access-Control-Allow-Origin', '*' if '*' in allowed else origin)
                self.send_header('Vary', 'Origin')
                self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')
                self.send_header('Access-Control-Max-Age', '86400')

        def _send(self, status, obj, extra=()):
            body = (json.dumps(obj, ensure_ascii=False, indent=None, separators=(',', ':')) + '\n').encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store' if self.command != 'GET' else 'public, max-age=60')
            self.send_header('X-Content-Type-Options', 'nosniff')
            for k, v in extra:
                self.send_header(k, v)
            self._cors()
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def _error(self, status, code, message, extra=None):
            err = {'code': code, 'message': message}
            if extra:
                err.update(extra)
            self._send(status, {'error': err})

        def _dispatch(self):
            u = urlsplit(self.path)
            path = u.path.rstrip('/') or '/'
            query = parse_qs(u.query, keep_blank_values=True)
            allowed = set()
            for method, rx, name in ROUTES:
                m = rx.match(path)
                if not m:
                    continue
                allowed.add(method)
                if method != self.command and not (method == 'GET' and self.command == 'HEAD'):
                    continue
                try:
                    with app.store.session():
                        status, obj = getattr(app, name)(Request(self, query), *m.groups())
                    self._send(status, obj)
                except CodeError as e:
                    extra = {'machine': e.machine} if getattr(e, 'machine', None) else None
                    self._error(e.status, e.code, e.message, extra)
                except Exception:
                    traceback.print_exc()
                    self._error(500, 'internal', 'The server could not answer this request.')
                return
            if allowed:
                self._error(405, 'method_not_allowed', '%s is not allowed here; use %s.' % (self.command, ', '.join(sorted(allowed))),)
            else:
                self._error(404, 'no_such_endpoint', 'There is no endpoint %s. See /v1/info and docs/api.md.' % path)

        def do_GET(self):
            self._dispatch()

        def do_HEAD(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

        def do_PATCH(self):
            self._dispatch()

        def do_PUT(self):
            self._dispatch()

        def do_DELETE(self):
            self._dispatch()

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.send_header('Content-Length', '0')
            self.end_headers()

    return Handler


def make_server(app, host, port):
    srv = ThreadingHTTPServer((host, port), make_handler(app))
    srv.daemon_threads = True
    return srv
