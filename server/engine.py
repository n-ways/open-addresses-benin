"""The address rules the server applies, on top of the reference engine.

Parsing, check digits, name keys, spot codes, plate-name forms and the
Hilbert key come from engine/reference/bj_engine.py unchanged. This module
adds what an issuer needs beyond the reference: the register of areas as it
stands in the database (with any extension blocks added since the export),
the "Add my home" numbering rule exactly as the N-Ways issuer applies it
(NextFree, NextBlock, Insert), the code area of a point, and the distances
the issuer uses.
"""
import math
import os
import re
import sys
import unicodedata

from . import REPO_DIR

sys.path.insert(0, os.path.join(REPO_DIR, 'engine', 'reference'))
import bj_engine as E  # noqa: E402
import bj_border as B  # noqa: E402

COUNTRY = 'BJ'

# Numbering (SPEC 5.1). The top third of an area's first block is its tail reserve.
MIN_BLOCK = E.MIN_BLOCK
MAX_BLOCK = E.MAX_BLOCK

# On-demand issue (SPEC 7).
PLACE_NEAR_M = 250.0   # a new home joins the area of the nearest issued code within this distance
FOUND_M = 12.0         # a point within this distance of a code's entrance is that code (/v1/at)
SPOT_FOUND_M = 15.0    # a spot code decodes to the code within this distance of its cell centre
SAME_BUILDING_M = 3.0  # a request this close to an issued entrance is the same building
DOOR_MAX_M = 80.0      # another door is at most this far from the code's entrance
MOVE_MAX_M = 80.0      # an entrance moves at most this far
MIN_AREA_M2 = 6.0      # a home's outline is between 6 m² ...
MAX_AREA_M2 = 20000.0  # ... and 2 ha
NEAR_MAX_M = 500.0
NEAR_MAX_RESULTS = 100

# Metres per degree on the local plane the issuer uses for outlines and nearest areas.
M_LAT = 110574.0
M_LON_EQ = 111320.0


class CodeError(ValueError):
    """A code or a request that cannot be answered, with a stable error code."""

    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


# ------------------------------------------------------------------ distances

_WGS84_A = 6378137.0
_WGS84_E2 = 0.00669437999014


def ground_m(lat1, lon1, lat2, lon2):
    """Distance in metres on the WGS 84 ellipsoid, with the meridian and prime-vertical
    radii at the mean latitude. Within a few hundred metres it agrees with a geodesic
    to well under a millimetre."""
    phi = math.radians((lat1 + lat2) / 2)
    s = math.sin(phi)
    w = math.sqrt(1 - _WGS84_E2 * s * s)
    m = _WGS84_A * (1 - _WGS84_E2) / w ** 3
    n = _WGS84_A / w
    return math.hypot(math.radians(lat2 - lat1) * m, math.radians(lon2 - lon1) * n * math.cos(phi))


def plane_m(lat1, lon1, lat2, lon2):
    """The issuer's distance for doors and entrance moves: 111,320 m per degree on
    both axes, longitude scaled by the cosine of the mean latitude."""
    dy = (lat2 - lat1) * 111320
    dx = (lon2 - lon1) * 111320 * math.cos((lat1 + lat2) / 2 * math.pi / 180)
    return math.hypot(dx, dy)


def area_m(lat1, lon1, lat2, lon2):
    """The issuer's distance from an area's place point (lat1, lon1) to a point."""
    return math.hypot((lat1 - lat2) * M_LAT, (lon1 - lon2) * M_LON_EQ * math.cos(lat2 * math.pi / 180))


def ring_area_m2(ring):
    """Area of a ring of (lon, lat) on the local plane of its first vertex."""
    if len(ring) < 3:
        return 0.0
    k = math.cos(ring[0][1] * math.pi / 180)
    a = 0.0
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        xi, yi = ring[i][0] * M_LON_EQ * k, ring[i][1] * M_LAT
        xj, yj = ring[j][0] * M_LON_EQ * k, ring[j][1] * M_LAT
        a += xi * yj - xj * yi
    return abs(a) / 2


def ring_perimeter_m(ring):
    return sum(plane_m(ring[i][1], ring[i][0], ring[(i + 1) % len(ring)][1], ring[(i + 1) % len(ring)][0])
               for i in range(len(ring)))


def ring_contains(ring, lon, lat):
    return E._in_ring(lon, lat, ring)


def ring_overlap_m2(r1, r2, samples=48):
    """Area shared by two rings, estimated on a regular grid over the overlap of their
    boxes (outlines are small; the 50 % rule below needs no more precision)."""
    x0 = max(min(p[0] for p in r1), min(p[0] for p in r2))
    x1 = min(max(p[0] for p in r1), max(p[0] for p in r2))
    y0 = max(min(p[1] for p in r1), min(p[1] for p in r2))
    y1 = min(max(p[1] for p in r1), max(p[1] for p in r2))
    if x0 >= x1 or y0 >= y1:
        return 0.0
    dx, dy = (x1 - x0) / samples, (y1 - y0) / samples
    hit = 0
    for i in range(samples):
        x = x0 + (i + 0.5) * dx
        for j in range(samples):
            y = y0 + (j + 0.5) * dy
            if ring_contains(r1, x, y) and ring_contains(r2, x, y):
                hit += 1
    cell = (dx * M_LON_EQ * math.cos(math.radians((y0 + y1) / 2))) * (dy * M_LAT)
    return hit * cell


# ------------------------------------------------------------------ Plus Codes

_OLC = '23456789CFGHJMPQRVWX'


def plus_code(lat, lng):
    """Open Location Code of a point, 11 characters ('6FR4995R+7CQ')."""
    def r6(x):
        return round(x * 1e6) / 1e6
    lat = min(90.0, max(-90.0, lat))
    lng = ((lng + 180) % 360 + 360) % 360 - 180
    lat_v = int(math.floor(r6((lat + 90) * 25000000)))
    lng_v = int(math.floor(r6((lng + 180) * 8192000)))
    code = ''
    for _ in range(5):
        code = _OLC[(lat_v % 5) * 4 + lng_v % 4] + code
        lat_v //= 5
        lng_v //= 4
    pairs = ''
    for _ in range(5):
        pairs = _OLC[lat_v % 20] + _OLC[lng_v % 20] + pairs
        lat_v //= 20
        lng_v //= 20
    full = pairs + code
    return full[:8] + '+' + full[8:11]


# ------------------------------------------------------------------ the register of areas

class Area(object):
    __slots__ = ('zone', 'id', 'plate', 'official', 'commune', 'arrondissement', 'departement', 'name_key',
                 'name_index', 'digits', 'blocks', 'provisional', 'point', 'frame', 'unit', 'arr_no', 'row')

    def __init__(self, row, extra_blocks=()):
        """row: an areas.csv record (dict of strings)."""
        self.row = row
        self.zone = row['zone']
        self.id = int(row['id'])
        self.plate = row['plate_name']
        self.official = row['official_name']
        self.commune = row['commune']
        self.arrondissement = row['arrondissement']
        self.departement = row['departement']
        self.name_key = row['name_key']
        self.name_index = int(row['name_index'])
        self.digits = int(row['digits'])
        self.blocks = parse_blocks(row['blocks'])
        for b in extra_blocks:
            if all(x[0] != b[0] for x in self.blocks):
                self.blocks.append(list(b))
        self.provisional = row['provisional_name'] == 'true'
        self.point = (float(row['place_lat']), float(row['place_lon'])) if row['place_lat'] else None
        self.frame = tuple(float(v) for v in row['frame'].split())
        self.unit = self.zone[:3]
        self.arr_no = int(self.zone[4:6])

    def copy(self):
        c = Area.__new__(Area)
        for k in Area.__slots__:
            setattr(c, k, getattr(self, k))
        c.blocks = [list(b) for b in self.blocks]
        return c

    def in_blocks(self, n):
        return any(lo <= n <= hi for lo, hi in self.blocks)

    def blocks_text(self):
        return '|'.join('%d-%d' % (lo, hi) for lo, hi in self.blocks)


def parse_blocks(text):
    out = []
    for part in text.split('|'):
        if part:
            lo, hi = part.split('-')
            out.append([int(lo), int(hi)])
    return out


class Register(object):
    """The areas in force: the frozen area table plus every block added since."""

    def __init__(self, areas):
        self.areas = sorted(areas, key=lambda a: a.id)
        self.by_zone = {a.zone: a for a in self.areas}
        self.by_id = {a.id: a for a in self.areas}
        self.families = {}
        self.in_arr = {}
        for a in sorted(self.areas, key=lambda a: a.zone):
            self.families.setdefault(a.name_key, []).append(a)
            self.in_arr.setdefault((a.unit, a.arr_no), []).append(a)
        self.sync_reference()

    def sync_reference(self):
        """Make the reference engine's name table carry the blocks in force, so its
        parsing and decoding see the extension blocks this register has added."""
        t = E.names()
        by_name = t['_byName']
        for nk, fam in self.families.items():
            e = by_name.get(nk)
            if e is None:
                a = fam[0]
                e = {'n': nk, 'p': a.plate, 'i': a.name_index, 'd': a.digits, 'q': None, 'b': []}
                t['names'].append(e)
                by_name[nk] = e
            e['b'] = [[a.zone, lo, hi - lo + 1] for a in fam for lo, hi in a.blocks]
        t['_byArea'] = {}
        for e in t['names']:
            for ak, first, size in e['b']:
                t['_byArea'].setdefault(ak, []).append((e, first, size))

    def add_block(self, zone, block):
        a = self.by_zone[zone]
        if all(b[0] != block[0] for b in a.blocks):
            a.blocks.append(list(block))
        self.sync_reference()

    # ---- the code area of a point (SPEC 3.1)

    def arrondissement_at(self, lat, lng):
        return E.arrondissement_at(lat, lng)

    def area_at(self, lat, lng):
        """The nearest place point of the point's arrondissement (ties to the lower area
        key), or the arrondissement's first area; None outside Benin."""
        arr = E.arrondissement_at(lat, lng)
        if arr is None:
            return None
        cand = self.in_arr.get((arr['commune'], arr['number']), [])
        best, bd = None, math.inf
        cl = math.cos(lat * math.pi / 180) ** 2
        for a in cand:
            if a.point is None:
                continue
            dx, dy = a.point[1] - lng, a.point[0] - lat
            d = dx * dx * cl + dy * dy
            if d < bd:
                best, bd = a, d
        if best is None and cand:
            best = cand[0]
        return best

    def nearest_area(self, lat, lng):
        """The numbered area whose place point is nearest (ties to the lower id)."""
        best, bd = None, math.inf
        for a in self.areas:
            if not a.blocks or a.point is None:
                continue
            d = area_m(a.point[0], a.point[1], lat, lng)
            if d < bd:
                best, bd = a, d
        return best

    # ---- numbering (SPEC 5)

    def next_block(self, a, compounds):
        """A full area takes an extension block of its name: the lowest free hundreds
        of the name's spare space, above every block of the name. The block is
        appended to a; None when the name has no room left."""
        size = min(MAX_BLOCK, max(MIN_BLOCK, (2 * compounds + 99) // 100 * 100))
        lo = 10 ** (a.digits - 1)
        hi = lo * 10 - 1
        at = lo
        for x in self.families.get(a.name_key, []):
            for b in x.blocks:
                at = max(at, b[1] + 1)
        if at + size - 1 > hi:
            return None
        b = [at, at + size - 1]
        a.blocks.append(b)
        return b

    def insert(self, a, issued, lat, lng):
        """A new compound's number in area a (a copy: a new block is appended to it),
        or None when the name is full. issued: [(number, lat, lng)] of every code
        the area has ever had, retired ones included (a number is never reused)."""
        n = next_free(a, issued, lat, lng)
        if n is not None:
            return n
        b = self.next_block(a, len(issued) + 1)
        return None if b is None else b[0]

    # ---- forms (SPEC 7)

    def forms(self, a, number):
        chk = E.check_digit(a.name_index, number)
        sp = E.spoken_number(number)
        return {'machine': 'BJ-%s-%d-%d' % (a.zone, number, chk), 'home': '%s %d' % (a.plate, number),
                'written': E.remembered(a.plate, number, provisional=True), 'spoken': '%s, %s' % (a.plate, sp),
                'check': chk}


def hilbert_of(a, lat, lng):
    return E.hilbert_key(a.frame, lng, lat)


def tail_start(a):
    lo, hi = a.blocks[0]
    return lo + (hi - lo + 1) * 2 // 3


def next_free(a, issued, lat, lng):
    """'Add my home' (SPEC 5, after issue): between the new home's neighbours on the
    curve (below the tail reserve), the free number nearest their midpoint, the lower
    first; else the lowest free number of the tail reserve; else of the area's later
    blocks. None when the area is full."""
    h = hilbert_of(a, lat, lng)
    tail = tail_start(a)
    used = set()
    seq = []
    for n, la, lo in issued:
        used.add(n)
        if n < tail:
            seq.append((hilbert_of(a, la, lo), n))
    seq.sort()
    first, hi = a.blocks[0]
    low_n, high_n = first - 1, tail
    found = False
    for kh, n in seq:
        if kh <= h:
            low_n = n
        elif not found:
            high_n, found = n, True
    if high_n - low_n > 1:
        mid = (low_n + high_n) // 2
        for d in range(high_n - low_n):
            for c in (mid - d, mid + d):
                if low_n < c < high_n and c not in used:
                    return c
    for c in range(tail, hi + 1):
        if c not in used:
            return c
    for lo2, hi2 in a.blocks[1:]:
        for c in range(lo2, hi2 + 1):
            if c not in used:
                return c
    return None


# ------------------------------------------------------------------ reading what people type

_MACHINE = re.compile(r'^BJ-([A-Z]{3})-(\d{2})-(\d{3})-(\d{4,5})(?:-(\d))?(?:\.(\d+))?(?:/(\d+))?$')
_SPOT = re.compile(r'^(?:BJ-)?([A-Z]{3})[- ](\d{2})(?:-S-| · | ·|\s+)([2-9CFGHJMPQRVWX ]+)$')
_PAIRS = re.compile(r'^\s*(.+?)\s+((?:\d\s?){3}\d(?:\s?\d)?)\s*(?:,\s*(.+?))?\s*$')


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


def upper_plain(text):
    return plain(text.strip()).upper()


def looks_machine(text):
    return bool(_MACHINE.match(upper_plain(text)))


def looks_spot(text):
    u = text.strip().upper()
    return bool(_SPOT.match(u)) and not _MACHINE.match(u)


def parse_machine(text):
    """A machine form ('BJ-COT-12-001-1807-4', check digit optional) checked by the
    reference engine against the blocks in force. Raises CodeError."""
    u = upper_plain(text)
    m = _MACHINE.match(u)
    if not m:
        raise CodeError('invalid_code', 'Not an N-Ways Benin machine code: expected BJ-CCC-AA-QQQ-NNNN-K.')
    core = 'BJ-%s-%s-%s-%s' % m.groups()[:4] + ('-' + m.group(5) if m.group(5) else '')
    try:
        p = E.parse_machine(core)
    except ValueError as e:
        msg = str(e)
        if 'check digit' in msg:
            raise CodeError('check_digit', 'The check digit does not match: a digit is wrong or two are swapped.', 422)
        if 'code area' in msg and 'national name table' in msg:
            raise CodeError('unknown_area', 'There is no code area %s-%s-%s.' % m.groups()[:3], 404)
        if 'commune' in msg:
            raise CodeError('unknown_area', 'There is no commune key %s.' % m.group(1), 404)
        raise CodeError('not_in_area', 'The number %s is not in code area %s-%s-%s: a digit is wrong.'
                        % (m.group(4), m.group(1), m.group(2), m.group(3)), 422)
    p['zone'] = '%s-%s-%s' % m.groups()[:3]
    p['hasCheck'] = m.group(5) is not None
    p['canonical'] = 'BJ-%s-%d-%d' % (p['zone'], p['number'], p['check'])
    return p


def parse_remembered(text):
    """(name, number, commune or None) of a remembered or written form, typed in any
    spacing ('Cadjéhoun · 18 07', 'cadjehoun 1807', 'Cadjéhoun 18 07, Cotonou')."""
    t = ' '.join(text.replace(' ', ' ').split())
    try:
        return E.parse_remembered(t)
    except ValueError:
        m = _PAIRS.match(t)
        if not m:
            raise CodeError('invalid_code', 'Expected a quartier or village name and a number of 4 or 5 digits.')
        return m.group(1), int(re.sub(r'\D', '', m.group(2))), m.group(3)


def resolve_remembered(reg, text):
    """The area and number a remembered form names, anywhere in Benin. A commune
    written after a comma must be the area's; it never chooses between areas."""
    name, number, commune = parse_remembered(text)
    name = name.rstrip(' ·.-')
    try:
        (com, arr_no, q), e = E.resolve(name, number)
    except ValueError as err:
        msg = str(err)
        if 'no code area is called' in msg:
            raise CodeError('unknown_name', 'No N-Ways area of Benin is called "%s".' % name.strip(), 404)
        if 'digits' in msg:
            raise CodeError('wrong_digits', msg[0].upper() + msg[1:] + '.', 422)
        raise CodeError('not_issued', '%s %s is not issued: no area of that name holds this number.'
                        % (name.strip(), E.spoken_number(number)), 404)
    a = reg.by_zone.get(E.area_key(com, arr_no, q))
    if a is None:
        raise CodeError('unknown_area', 'The area of %s %s is not in this register.' % (name, number), 404)
    if commune and E.norm_name(commune) != E.norm_name(a.commune):
        raise CodeError('wrong_commune', '%s %s is in %s, not %s.' % (a.plate, E.spoken_number(number), a.commune, commune), 404)
    return a, number


def in_country(lat, lng):
    """The point is in Benin: within 300 m of the national border (SPEC 1b), and in an
    arrondissement outline, or in none but given a spot code by SPEC 2.4, as the compounds
    in the slivers between outlines and along the border rivers are. The border decides:
    an outline or a spot frame that reaches over it gives no Benin code there."""
    return not abroad(lat, lng) and E.spot_arrondissement(lat, lng) is not None


def abroad(lat, lng):
    """The point lies more than 300 m outside Benin's national border (OpenStreetMap
    admin_level 2), as engine/data/border.json can tell with its simplification margin."""
    return B.abroad(lat, lng)


def spot(lat, lng):
    return E.spot_encode(lat, lng)


def spot_decode(code):
    try:
        return E.spot_decode(code)
    except ValueError as e:
        raise CodeError('invalid_spot', str(e)[0].upper() + str(e)[1:] + '.', 400)


def spot_of_code(code):
    """A spot code in both forms and its cell centre, in the frame of the arrondissement it
    names (no lookup: a point in no outline keeps the arrondissement it was encoded in)."""
    lat, lng = spot_decode(code)
    arr, _m = E.spot_arrondissement_of(code)
    return E.spot_encode(lat, lng, arr), lat, lng


def spot_display(lat, lng):
    try:
        return E.spot_encode(lat, lng)['display']
    except ValueError:
        return ''


def norm_name(text):
    return E.norm_name(text)


def norm_address(text):
    """Key of an official address for lookup: case, accents and spacing folded."""
    return ' '.join(plain(text).lower().replace(',', ' , ').split()).replace(' ,', ',')
