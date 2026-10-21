#!/usr/bin/env python3
"""N-Ways address engine for Benin: reference implementation (standard library only).

This is Benin's own engine (engine/SPEC.md). It is not shared with any other
country. It does six things:

  1. Spot codes: any point in Benin to a short code and back, on a 3 m grid in
     UTM zone 31N (WGS 84, EPSG:32631), inside the arrondissement's frame.
  2. Code areas: which commune, arrondissement and quartier/village a point is in
     (model/keys.json + model/units/arrondissements.geojson).
  3. Compounds: groups building footprints into compounds (concessions) before
     numbering: mapped enclosures (walls, fences), annexes attached to the main
     house, everything else on its own.
  4. Numbering: compound numbers along a Hilbert curve with reserved gaps and a
     tail reserve; provisional numbers for new homes ("Ajouter ma maison").
  5. National name ranges: every code area sharing a normalised PLATE name
     draws from one national range for that name (model/names.json), so
     "Zogbo · 46 17" names one compound in all of Benin with no commune; Damm
     check digit over the national name index and the number. The plate name is
     the short remembered name of the area (at most 12 characters and 2 words,
     plate_names.py); the official name is kept for small print and still
     decodes as an alias when it maps to one plate name.
  6. Parsing and formatting of the remembered form ("Zogbo 46 17"), the written
     form and the machine form ("BJ-COT-09-004-4617-4").

Command line:
  bj_engine.py spot LAT LON          spot code of a point
  bj_engine.py unspot CODE           centre of a spot code
  bj_engine.py area LAT LON          code area (commune, arrondissement, quartier)
  bj_engine.py check DIGITS          Damm check digit
  bj_engine.py parse CODE            parse a machine code
  bj_engine.py find "NAME NUMBER"    remembered form -> the one code area in Benin
  bj_engine.py demo                  group and number the Cotonou sample
"""
import json
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
KEYS_PATH = os.path.join(REPO, 'model', 'keys.json')
NAMES_PATH = os.path.join(REPO, 'model', 'names.json')
ARR_PATH = os.path.join(REPO, 'model', 'units', 'arrondissements.geojson')

sys.path.insert(0, HERE)
import plate_names as _P  # noqa: E402

# Benin settings of the plate rule: names carry ordinals ("Ganvié 1", kept apart
# from the number by '·'), and "Es" (Arabic article, "Dar Es Salam") links words.
_P.DIGITS_OK = True
_P.LINKING['fr'] = _P.LINKING['fr'] | {'es'}
PLATE_LANG = 'fr'

# Spot-code alphabet: 20 characters, no vowels, no 0/O 1/I/L look-alikes.
ALPHABET = '23456789CFGHJMPQRVWX'
CELL_M = 3.0

# ---------------------------------------------------------------- Damm check

DAMM = (
    (0, 3, 1, 7, 5, 9, 8, 6, 4, 2),
    (7, 0, 9, 2, 1, 5, 4, 8, 6, 3),
    (4, 2, 0, 6, 8, 7, 1, 3, 5, 9),
    (1, 7, 5, 0, 9, 8, 3, 4, 2, 6),
    (6, 1, 2, 3, 0, 4, 5, 9, 7, 8),
    (3, 6, 7, 4, 2, 0, 9, 5, 8, 1),
    (5, 8, 6, 9, 7, 2, 0, 1, 3, 4),
    (8, 9, 4, 5, 3, 6, 2, 0, 1, 7),
    (9, 4, 3, 8, 6, 1, 7, 2, 0, 5),
    (2, 5, 8, 1, 4, 3, 6, 7, 9, 0),
)


def damm(digits):
    """Damm check digit of a string of decimal digits."""
    interim = 0
    for c in digits:
        interim = DAMM[interim][int(c)]
    return interim


def damm_ok(digits_with_check):
    return damm(digits_with_check) == 0


# ------------------------------------------------------- UTM zone 31N (WGS84)
# Krüger series (order n^3), accurate to well under a millimetre in Benin.

_A = 6378137.0
_F = 1 / 298.257223563
_N = _F / (2 - _F)
_AA = _A / (1 + _N) * (1 + _N ** 2 / 4 + _N ** 4 / 64)
_ALPHA = (_N / 2 - 2 * _N ** 2 / 3 + 5 * _N ** 3 / 16, 13 * _N ** 2 / 48 - 3 * _N ** 3 / 5, 61 * _N ** 3 / 240)
_BETA = (_N / 2 - 2 * _N ** 2 / 3 + 37 * _N ** 3 / 96, _N ** 2 / 48 + _N ** 3 / 15, 17 * _N ** 3 / 480)
_DELTA = (2 * _N - 2 * _N ** 2 / 3 - 2 * _N ** 3, 7 * _N ** 2 / 3 - 8 * _N ** 3 / 5, 56 * _N ** 3 / 15)
_K0, _E0, _LON0 = 0.9996, 500000.0, math.radians(3.0)
_C = 2 * math.sqrt(_N) / (1 + _N)


def to_utm(lat, lon):
    """WGS84 latitude/longitude (degrees) to UTM 31N easting/northing (metres)."""
    phi, dl = math.radians(lat), math.radians(lon) - _LON0
    t = math.sinh(math.atanh(math.sin(phi)) - _C * math.atanh(_C * math.sin(phi)))
    xi = math.atan2(t, math.cos(dl))
    eta = math.atanh(math.sin(dl) / math.sqrt(1 + t * t))
    e = eta + sum(a * math.cos(2 * j * xi) * math.sinh(2 * j * eta) for j, a in enumerate(_ALPHA, 1))
    n = xi + sum(a * math.sin(2 * j * xi) * math.cosh(2 * j * eta) for j, a in enumerate(_ALPHA, 1))
    return _E0 + _K0 * _AA * e, _K0 * _AA * n


def from_utm(e, n):
    """UTM 31N easting/northing (metres) to WGS84 latitude/longitude (degrees)."""
    xi, eta = n / (_K0 * _AA), (e - _E0) / (_K0 * _AA)
    xi2 = xi - sum(b * math.sin(2 * j * xi) * math.cosh(2 * j * eta) for j, b in enumerate(_BETA, 1))
    eta2 = eta - sum(b * math.cos(2 * j * xi) * math.sinh(2 * j * eta) for j, b in enumerate(_BETA, 1))
    chi = math.asin(math.sin(xi2) / math.cosh(eta2))
    phi = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(_DELTA, 1))
    lam = _LON0 + math.atan2(math.sinh(eta2), math.cos(xi2))
    return math.degrees(phi), math.degrees(lam)


# ------------------------------------------------------------------ data

_keys = None
_polys = None


def _load(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def keys():
    global _keys
    if _keys is None:
        _keys = _load(KEYS_PATH)
        _keys['_arr'] = {a['id']: a for a in _keys['arrondissements']}
        _keys['_byCode'] = {(a['commune'], a['number']): a for a in _keys['arrondissements']}
        _keys['_com'] = {c['key']: c for c in _keys['communes']}
    return _keys


def _rings(geom):
    if geom['type'] == 'Polygon':
        return [geom['coordinates']]
    return geom['coordinates']


def polygons():
    global _polys
    if _polys is None:
        _polys = []
        for f in _load(ARR_PATH)['features']:
            ps = _rings(f['geometry'])
            xs = [p[0] for poly in ps for p in poly[0]]
            ys = [p[1] for poly in ps for p in poly[0]]
            _polys.append((f['properties']['id'], ps, (min(xs), min(ys), max(xs), max(ys))))
    return _polys


def _in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _in_polygon(x, y, poly):
    return _in_ring(x, y, poly[0]) and not any(_in_ring(x, y, h) for h in poly[1:])


def arrondissement_at(lat, lon):
    """The arrondissement record containing the point, or None (outside Benin)."""
    for aid, ps, (x0, y0, x1, y1) in polygons():
        if x0 <= lon <= x1 and y0 <= lat <= y1 and any(_in_polygon(lon, lat, p) for p in ps):
            return keys()['_arr'].get(aid)
    return None


# ------------------------------------------------------------- spot codes

def _digits(v, k):
    out = []
    for _ in range(k):
        out.append(v % 20)
        v //= 20
    return out[::-1]


SPOT_NEAR_CELLS = 333      # a point at most 999 m beyond a frame takes the frame's nearest cell
SPOT_OUTLINE_M = 10000.0   # a point in no outline is in Benin when an outline lies within 10 km
M_PER_DEG_LAT = 110574.0   # metres per degree of latitude, for distances to outlines


def _cells(e, n, arr):
    """Cell (ix, iy) of a UTM point in an arrondissement's frame; either may fall outside it."""
    return int((e - arr['e0']) // CELL_M), int((n - arr['n0']) // CELL_M)


def _beyond(v, k):
    """Cells by which an index lies outside 0 .. 20^k - 1 (0 inside)."""
    return -v if v < 0 else max(0, v - (20 ** k - 1))


def edge_d2(lat, lon, polys):
    """Squared distance from a point to the nearest edge of any ring of an outline, in degrees
    of latitude, with longitude differences scaled by cos(latitude of the point)."""
    c = math.cos(math.radians(lat))
    best = math.inf
    for poly in polys:
        for ring in poly:
            j = len(ring) - 1
            for i in range(len(ring)):
                ax, ay = (ring[j][0] - lon) * c, ring[j][1] - lat
                vx, vy = (ring[i][0] - lon) * c - ax, (ring[i][1] - lat) - ay
                ll = vx * vx + vy * vy
                t = 0.0
                if ll > 0:
                    t = min(1.0, max(0.0, -(ax * vx + ay * vy) / ll))
                px, py = ax + t * vx, ay + t * vy
                d = px * px + py * py
                if d < best:
                    best = d
                j = i
    return best


def spot_arrondissement(lat, lon):
    """Arrondissement of the spot grid for a point (SPEC 2.4): the one whose outline holds it;
    else, among those whose outline lies within 10 km and whose frame holds the point, the one
    with the nearest outline; else, among those whose outline lies within 10 km and whose frame
    the point lies at most 333 cells (999 m) beyond on each axis, the one with the nearest
    outline (the point then takes that frame's nearest cell); ties to the lower commune key,
    then the lower number. None: refused."""
    arr = arrondissement_at(lat, lon)
    if arr is not None:
        return arr
    e, n = to_utm(lat, lon)
    lim = SPOT_OUTLINE_M / M_PER_DEG_LAT
    lim = lim * lim
    best = None
    for aid, ps, _box in polygons():
        a = keys()['_arr'].get(aid)
        if a is None:
            continue
        ix, iy = _cells(e, n, a)
        over = max(_beyond(ix, a['kx']), _beyond(iy, a['ky']))
        if over > SPOT_NEAR_CELLS:
            continue
        d = edge_d2(lat, lon, ps)
        if d > lim:
            continue
        k = (over > 0, d, a['commune'], a['number'])
        if best is None or k < best[0]:
            best = (k, a)
    return best[1] if best else None


def spot_encode(lat, lon, arr=None):
    """Spot code of a point: {'machine', 'display', 'arrondissement'}; arr: its arrondissement
    for the grid (default: spot_arrondissement)."""
    arr = arr or spot_arrondissement(lat, lon)
    if arr is None:
        raise ValueError('point outside Benin: in no arrondissement, and none within 10 km has a frame within 999 m')
    e, n = to_utm(lat, lon)
    ix, iy = _cells(e, n, arr)
    kx, ky = arr['kx'], arr['ky']
    if max(_beyond(ix, kx), _beyond(iy, ky)) > SPOT_NEAR_CELLS:
        raise ValueError('point more than 999 m beyond the arrondissement frame')
    ix = min(max(ix, 0), 20 ** kx - 1)
    iy = min(max(iy, 0), 20 ** ky - 1)
    body = _interleave(_digits(iy, ky), _digits(ix, kx))
    s = ''.join(ALPHABET[d] for d in body)
    head = f"{arr['commune']}-{arr['number']:02d}"
    return {'machine': f'BJ-{head}-S-{s}', 'display': f"{arr['commune']} {arr['number']:02d} · {s[:3]} {s[3:]}",
            'arrondissement': arr['name'], 'commune': keys()['_com'][arr['commune']]['name']}


def _interleave(dy, dx):
    k = max(len(dy), len(dx))
    dy = [None] * (k - len(dy)) + dy
    dx = [None] * (k - len(dx)) + dx
    out = []
    for a, b in zip(dy, dx):
        if a is not None:
            out.append(a)
        if b is not None:
            out.append(b)
    return out


def spot_arrondissement_of(code):
    """The arrondissement a spot code names, and its characters: no lookup, since a spot code
    is decoded in the frame of the arrondissement it names."""
    m = re.fullmatch(r'(?:BJ-)?([A-Z]{3})[- ](\d{2})(?:-S-| · | ·|\s+)([2-9CFGHJMPQRVWX ]+)', code.strip().upper())
    if not m:
        raise ValueError('not a Benin spot code')
    arr = keys()['_byCode'].get((m.group(1), int(m.group(2))))
    if arr is None:
        raise ValueError('unknown commune/arrondissement')
    return arr, m


def spot_decode(code):
    """Centre (lat, lon) of a spot code 'BJ-COT-12-S-XXXXXX' or 'COT 12 · XXX XXX'."""
    arr, m = spot_arrondissement_of(code)
    s = m.group(3).replace(' ', '')
    kx, ky = arr['kx'], arr['ky']
    if len(s) != kx + ky:
        raise ValueError(f'spot code here has {kx + ky} characters')
    vals = [ALPHABET.index(c) for c in s]
    k = max(kx, ky)
    ix = iy = 0
    pos = 0
    for level in range(k):
        if level >= k - ky:
            iy = iy * 20 + vals[pos]
            pos += 1
        if level >= k - kx:
            ix = ix * 20 + vals[pos]
            pos += 1
    e = arr['e0'] + (ix + 0.5) * CELL_M
    n = arr['n0'] + (iy + 0.5) * CELL_M
    return from_utm(e, n)


# ------------------------------------------------------------- code areas

def code_area(lat, lon):
    """Commune, arrondissement and quartier/village of a point: the nearest named
    place of its arrondissement (SPEC 3.1)."""
    arr = arrondissement_at(lat, lon)
    if arr is None:
        return None
    best = None
    for p in arr['places']:
        d = (p['lon'] - lon) ** 2 * math.cos(math.radians(lat)) ** 2 + (p['lat'] - lat) ** 2
        if best is None or d < best[0]:
            best = (d, p)
    place = best[1] if best else {'index': 0, 'name': arr['name']}
    return {'commune': arr['commune'], 'communeName': keys()['_com'][arr['commune']]['name'],
            'arrondissement': arr['number'], 'arrondissementName': arr['name'],
            'quartier': place['index'], 'quartierName': place['name'], 'plateName': plate_of_place(arr, place),
            'digits': arr.get('digits', 4)}


def plate_of_place(arr, place):
    """Plate name of a code area: the place's 'plate' field when it differs from
    the official name, else the official name. Area 000 (an arrondissement with
    no named place) keeps its plate on the arrondissement record."""
    if place.get('index', 0) == 0 and not arr['places']:
        return arr.get('plate', arr['name'])
    return place.get('plate', place['name'])


def plate_ok(name):
    """True if a plate name keeps the plate limit: at most 12 characters (an
    accented letter, a space, a hyphen or an apostrophe counts one) and at most
    2 words (linking words such as de, la, les do not count)."""
    return _P.fits(name, PLATE_LANG)


# ------------------------------------------------- national name ranges
# "Zogbo · 46 17" must name ONE compound in the whole of Benin on its own, with
# no commune and no app position: a code is said on the phone and written on a
# parcel far from where it was issued, and one area in four shares its name with
# another. All code areas that share a normalised name therefore draw from one
# national range for that name, cut into frozen blocks (one per area) with spare
# room for future areas of the name.

_FOLD = {'ɔ': 'o', 'Ɔ': 'o', 'ɛ': 'e', 'Ɛ': 'e', 'ɖ': 'd', 'Ɖ': 'd', 'ŋ': 'ng', 'Ŋ': 'ng', 'œ': 'oe', 'æ': 'ae',
         'ƒ': 'f', 'ʋ': 'v', 'ɣ': 'g'}
_ROMAN = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}
_ORDINAL = re.compile(r'^(\d+)(?:er|ere|eme|e|ieme|nd|nde)$')
_ARTICLES = ('le', 'la', 'les', 'l')
_SAINTS = {'st': 'saint', 'ste': 'sainte'}   # abbreviations allowed on plates expand back


def norm_name(name):
    """Normalised key of a quartier/village name (French + Gbe/Yoruba/Bariba spellings).

    1. Fold case and accents (é è ê -> e, ô -> o...), and the Gbe letters
       ɔ -> o, ɛ -> e, ɖ -> d, ŋ -> ng.
    2. Hyphens, apostrophes, dots and spaces separate words only.
    3. A leading French article (le, la, les, l') is dropped.
    4. A trailing ordinal is a digit: 'Ganvié I', 'Ganvié 1er', 'Ganvié 1' -> ganvie1.
    5. Spelling variants of the same sound are folded: tch -> c (Fon c = tch),
       dj -> j, ou before a vowel -> w (Ouidah/Widah, Houéyiho/Hwéyiho),
       ph -> f, doubled letters -> one (Dassa/Dasa).
    6. Words are joined: 'Ouémè Hounli' = 'Ouèmèhounli'. The plate abbreviations
       St and Ste are read as Saint and Sainte ('St Prosper' = 'Saint Prosper').
    Two areas with the same key share one national number range."""
    s = ''.join(_FOLD.get(c, c) for c in name)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    words = [_SAINTS.get(w, w) for w in re.split(r"[^0-9a-z]+", s) if w]
    if len(words) > 1 and words[0] in _ARTICLES:
        words = words[1:]
    if len(words) > 1:
        last = words[-1]
        m = _ORDINAL.match(last)
        if last in _ROMAN:
            words[-1] = _ROMAN[last]
        elif m:
            words[-1] = m.group(1)
    s = ''.join(words)
    s = s.replace('tch', 'c').replace('dj', 'j').replace('ph', 'f')
    s = re.sub(r'ou(?=[aeiy])', 'w', s)
    s = re.sub(r'([a-z])\1+', r'\1', s)
    return s


BLOCK_UNIT = 100        # blocks start and end on hundreds
MIN_BLOCK = 200         # smallest block (a hamlet of up to 100 compounds)
MAX_BLOCK = 85000       # the largest block a five-digit name can hold beside its spare (90,000 - 5,000)
SPARE = {4: 500, 5: 5000}  # spare room a name keeps for its future areas


def block_size(compounds):
    """Block for one area: twice today's compounds (the capacity rule), on hundreds."""
    return max(MIN_BLOCK, -(-2 * compounds // BLOCK_UNIT) * BLOCK_UNIT)


def name_digits(total_blocks):
    """Digits of a name's range: 4 when its blocks + spare fit 1000-9999, else 5
    (10000-99999), else None (the name needs a qualifier, see QUALIFIERS)."""
    for d in (4, 5):
        if total_blocks + SPARE[d] <= 9 * 10 ** (d - 1):
            return d
    return None


# Names whose areas together do not fit 5 digits are split ONCE, by one
# established qualifier people already say, and listed here. No Benin name needs
# one: the largest range of any name (Ladji Farani, Parakou) holds 46,100 of
# its 90,000 numbers (model/stats/name-ranges.json, "qualified").
QUALIFIERS = {}


def allocate_names(groups):
    """groups: {normalised name: [{'key': (commune, arr, quartier), 'name', 'compounds'}]}.
    Returns [(normalised name, {'digits', 'blocks': [(key, first, size)], 'spare'})]
    sorted by name. Blocks are laid out from the bottom of the range in the order
    of the area keys; the top of the range is the name's spare space."""
    out = []
    for nk in sorted(groups):
        g = sorted(groups[nk], key=lambda a: a['key'])
        sizes = [min(MAX_BLOCK, block_size(a['compounds'])) for a in g]
        d = name_digits(sum(sizes))
        if d is None:
            raise ValueError(f'{nk}: {len(g)} areas do not fit 5 digits; add it to QUALIFIERS')
        lo = 10 ** (d - 1)
        blocks, at = [], lo
        for a, z in zip(g, sizes):
            blocks.append((a['key'], at, z))
            at += z
        out.append((nk, {'digits': d, 'blocks': blocks, 'spare': 10 ** d - at}))
    return out


_names = None


def names():
    """The national name table (model/names.json), indexed."""
    global _names
    if _names is None:
        t = _load(NAMES_PATH)
        t['_byName'] = {e['n']: e for e in t['names']}
        t['_alias'] = t.get('aliases', {})
        t['_byArea'] = {}
        for e in t['names']:
            for ak, first, size in e['b']:
                t['_byArea'].setdefault(ak, []).append((e, first, size))
        _names = t
    return _names


def area_key(commune, arr_no, quartier):
    return f'{commune}-{arr_no:02d}-{quartier:03d}'


def area_blocks(commune, arr_no, quartier):
    """(name entry, [(first, size)]) of a code area. An area keeps its first block and
    any extension blocks it was given later, all inside its name's range."""
    found = names()['_byArea'].get(area_key(commune, arr_no, quartier))
    if not found:
        raise ValueError('code area not in the national name table')
    return found[0][0], [(f, z) for _, f, z in found]


def resolve(name, number):
    """Name + number -> the one code area in Benin: (commune, arr, quartier), name entry.
    Raises if the name is unknown or the number is in no issued block of that name."""
    t = names()
    k = norm_name(name)
    e = t['_byName'].get(k) or t['_byName'].get(t['_alias'].get(k))
    if e is None:
        raise ValueError(f'no code area is called "{name}"')
    if len(str(number)) != e['d']:
        raise ValueError(f'numbers of "{name}" have {e["d"]} digits')
    for ak, first, size in e['b']:
        if first <= number < first + size:
            c, a, q = ak.split('-')
            return (c, int(a), int(q)), e
    raise ValueError(f'"{name} {number}" is in the spare space of the name: not issued')


def next_block(entry, compounds):
    """Block for a new area (or an extension of a full one) with an existing name:
    the lowest free hundreds of the name's spare space. Existing blocks never move."""
    lo, hi = 10 ** (entry['d'] - 1), 10 ** entry['d']
    at = max([first + size for _, first, size in entry['b']] + [lo])
    z = min(MAX_BLOCK, block_size(compounds))
    if at + z > hi:
        raise ValueError('the name has no spare room left: the new area takes its listed qualifier')
    return at, z


def check_digit(name_index, number):
    """Damm over the national name index (5 digits) and the number (5 digits, zero-padded).
    Name + number fix the area through the frozen block table, so the check digit
    binds name, number and area; the area digits of the machine form are verified
    against that table rather than fed into the sum, which keeps Damm's guarantee
    (every single wrong digit and every adjacent swap in the number is caught, even
    one that would point into another area of the same name)."""
    return damm(f'{name_index:05d}{number:05d}')


# ---------------------------------------------------------- code formats

def machine(commune, arr_no, quartier, number):
    """Machine code of a compound. The number must lie in one of the area's blocks."""
    e, blocks = area_blocks(commune, arr_no, quartier)
    if not any(f <= number < f + z for f, z in blocks):
        raise ValueError('number outside the blocks of this code area')
    return f'BJ-{commune}-{arr_no:02d}-{quartier:03d}-{number}-{check_digit(e["i"], number)}'


def parse_machine(code):
    m = re.fullmatch(r'BJ-([A-Z]{3})-(\d{2})-(\d{3})-(\d{4,5})(?:-(\d))?', code.strip().upper())
    if not m:
        raise ValueError('not a Benin compound code')
    com, arr_no, q, num, chk = m.groups()
    arr_no, q, num = int(arr_no), int(q), int(num)
    if com not in keys()['_com']:
        raise ValueError('unknown commune key')
    e, blocks = area_blocks(com, arr_no, q)
    if not any(f <= num < f + z for f, z in blocks):
        raise ValueError('the number is not in this code area: a digit is wrong')
    want = check_digit(e['i'], num)
    if chk is not None and int(chk) != want:
        raise ValueError('check digit does not match: a digit is wrong or two are swapped')
    return {'commune': com, 'arrondissement': arr_no, 'quartier': q, 'number': num, 'check': want}


def spoken_number(number):
    """'4817' -> '48 17' (two pairs, as phone numbers are read);
    '15170' -> '15 170' (a pair and a hundred, as French postcodes are read)."""
    s = str(number)
    if len(s) in (4, 5):
        return f'{s[:2]} {s[2:]}'
    return s


def remembered(plate_name, number, provisional=False):
    """Written remembered form: 'Zogbo · 48 17'. The '·' keeps names that end in a
    digit ('Ganvié 1', 'Adja 2') apart from the number. The name MUST be the
    area's plate name: a name over the limit (12 characters, 2 words) is refused,
    unless it is the provisional name of an area its commune may still rename.
    Such an area is issued under its provisional name all the same, so that no
    home waits for a naming decision; a later name is added as an alias."""
    if not plate_ok(plate_name) and not provisional:
        raise ValueError(f'"{plate_name}" is over the plate-name limit (12 characters, 2 words)')
    return f'{plate_name} · {spoken_number(number)}'


def parse_remembered(text):
    """'Zogbo 48 17' or 'Zogbo 4817, Cotonou' -> (name, number, commune name or None)."""
    m = re.fullmatch(r'\s*(.+?)\s*·\s*(\d{2}\s?\d{2,3})\s*(?:,\s*(.+?))?\s*', text) or \
        re.fullmatch(r'\s*(.+?)\s+(\d{2}\s\d{2,3}|\d{4,5})\s*(?:,\s*(.+?))?\s*', text)
    if not m:
        raise ValueError('expected "<quartier> <number>"')
    return m.group(1), int(m.group(2).replace(' ', '')), m.group(3)


def decode_remembered(text):
    """The remembered form alone -> the one code area and machine code in Benin.
    No commune and no position is needed. A commune written after a comma is
    accepted only if it is the right one (it is never needed to choose)."""
    name, number, commune = parse_remembered(text)
    (com, arr_no, q), e = resolve(name, number)
    if commune and norm_name(commune) != norm_name(keys()['_com'][com]['name']):
        raise ValueError(f'"{name} {number}" is in {keys()["_com"][com]["name"]}, not {commune}')
    arr = keys()['_byCode'][(com, arr_no)]
    place = next((p for p in arr['places'] if p['index'] == q), {'name': arr['name'], 'index': 0})
    plate = plate_of_place(arr, place)
    return {'commune': com, 'communeName': keys()['_com'][com]['name'], 'arrondissement': arr_no,
            'arrondissementName': arr['name'], 'quartier': q, 'quartierName': place['name'], 'plateName': plate,
            'number': number, 'machine': machine(com, arr_no, q, number),
            'at': [place.get('lat'), place.get('lon')]}


FRENCH_UNITS = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze',
                'treize', 'quatorze', 'quinze', 'seize']
FRENCH_TENS = {2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante', 8: 'quatre-vingt'}


def french_pair(n):
    """0-99 in French as read in phone numbers ('48' -> 'quarante-huit')."""
    if n < 17:
        return FRENCH_UNITS[n]
    if n < 20:
        return 'dix-' + FRENCH_UNITS[n - 10]
    t, u = divmod(n, 10)
    if t in (7, 9):
        base = FRENCH_TENS[t - 1]
        rest = n - (t - 1) * 10
        joiner = ' et ' if rest == 11 and t == 7 else '-'
        return base + joiner + french_pair(rest)
    base = FRENCH_TENS[t]
    if u == 0:
        return base + ('s' if t == 8 else '')
    if u == 1 and t != 8:
        return base + ' et un'
    return base + '-' + FRENCH_UNITS[u]


def _pair_fr(p):
    """A two-digit group as read in phone numbers: '03' -> 'zéro trois', '00' -> 'zéro zéro'."""
    if p[0] == '0':
        return 'zéro ' + FRENCH_UNITS[int(p[1])]
    return french_pair(int(p))


def _hundreds_fr(g):
    """A three-digit group as read in French postcodes: '170' -> 'cent soixante-dix',
    '205' -> 'deux cent cinq', '300' -> 'trois cents', '070' -> 'zéro soixante-dix'."""
    if g[0] == '0':
        return 'zéro ' + _pair_fr(g[1:])
    h, rest = int(g[0]), int(g[1:])
    head = 'cent' if h == 1 else FRENCH_UNITS[h] + (' cents' if rest == 0 else ' cent')
    return head if rest == 0 else f'{head} {french_pair(rest)}'


def say_fr(number):
    """French reading: 4817 -> 'quarante-huit dix-sept' (two pairs); 1203 -> 'douze zéro trois';
    15170 -> 'quinze cent soixante-dix' (a pair and a hundred, like a postcode)."""
    s = str(number)
    if len(s) == 5:
        return f'{_pair_fr(s[:2])} {_hundreds_fr(s[2:])}'
    return ' '.join(_pair_fr(s[i:i + 2]) for i in range(0, len(s), 2))


def display_address(record):
    """What is shown first for a compound record: the State's address where one
    exists, exactly as written; otherwise the N-Ways code.

    record: {'official': {'text': 'N° 43, Rue 12.217', ...} or None,
             'areaName': 'Zogbo' (the plate name), 'number': 4817, 'interim': bool}
    Returns (text, source): source is 'official', 'nways' or 'nways-interim'
    ('interim' marks a code shown where an official door number exists but is not
    yet known). The compound keeps its N-Ways code beside an official address."""
    off = record.get('official')
    if off and off.get('text'):
        return off['text'], 'official'
    text = remembered(record['areaName'], record['number'])
    return text, ('nways-interim' if record.get('interim') else 'nways')


# ------------------------------------------------------------- geometry

def _local(lat0):
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 110574.0
    return kx, ky


def ring_metrics(ring):
    """Area (m²), perimeter (m) and centroid (lon, lat) of a lon/lat ring (planar, local)."""
    lat0 = sum(p[1] for p in ring) / len(ring)
    kx, ky = _local(lat0)
    pts = [(p[0] * kx, p[1] * ky) for p in ring]
    a = cx = cy = 0.0
    per = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        cr = x1 * y2 - x2 * y1
        a += cr
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
        per += math.hypot(x2 - x1, y2 - y1)
    a /= 2
    if abs(a) < 1e-9:
        return 0.0, per, (ring[0][0], ring[0][1])
    return abs(a), per, (cx / (6 * a) / kx, cy / (6 * a) / ky)


def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def gap_m(r1, r2):
    """Smallest distance between two footprints' outlines in metres (0 if they touch or overlap)."""
    lat0 = r1[0][1]
    kx, ky = _local(lat0)
    p1 = [(x * kx, y * ky) for x, y in r1]
    p2 = [(x * kx, y * ky) for x, y in r2]
    if _in_ring(p1[0][0], p1[0][1], p2) or _in_ring(p2[0][0], p2[0][1], p1):
        return 0.0
    d = min(_seg_dist(p, p2[i], p2[(i + 1) % len(p2)]) for p in p1 for i in range(len(p2)))
    d = min(d, min(_seg_dist(p, p1[i], p1[(i + 1) % len(p1)]) for p in p2 for i in range(len(p1))))
    return d


# ------------------------------------------------------- building profile

CLASS_FROM_TAG = {
    'house': 'residential', 'residential': 'residential', 'detached': 'residential', 'apartments': 'residential',
    'hut': 'residential', 'stilt_house': 'residential', 'terrace': 'residential',
    'commercial': 'commercial', 'retail': 'commercial', 'kiosk': 'commercial', 'office': 'office', 'hotel': 'hospitality',
    'school': 'education', 'college': 'education', 'university': 'education', 'hospital': 'health', 'clinic': 'health',
    'church': 'religious', 'mosque': 'religious', 'government': 'government', 'public': 'government',
    'industrial': 'industrial', 'warehouse': 'industrial', 'hangar': 'industrial', 'construction': 'under_construction',
    'ruins': 'ruin', 'shed': 'annex', 'roof': 'annex', 'garage': 'transport',
}


def floors_from_height(h):
    """Floors from an OpenStreetMap height (m): h / 3, rounded, at least 1."""
    return max(1, int(round(h / 3.0)))


def profile(feature):
    """Structure profile from one footprint feature (properties: building, name, h)."""
    ring = _rings(feature['geometry'])[0][0]
    area, per, c = ring_metrics(ring)
    p = feature.get('properties') or {}
    tag = p.get('building')
    if tag and tag != 'yes' and tag in CLASS_FROM_TAG:
        cls, conf, src = CLASS_FROM_TAG[tag], 0.85, 'osm:building'
    elif area < 6:
        cls, conf, src = 'annex', 0.4, 'size'
    elif area > 2500:
        cls, conf, src = 'industrial', 0.3, 'size'
    else:
        cls, conf, src = 'residential', 0.45, 'default'
    # Floors from OpenStreetMap only: the Google/Microsoft height `h` is a rendering
    # filler (36 values spread over 3.5-7 m) and never gives floors.
    lv, h = p.get('building:levels'), p.get('height')
    try:
        fl, fsrc = (max(1, int(round(float(lv)))), 'osm:building:levels') if lv else \
            (floors_from_height(float(h)), 'osm:height') if h else (1, 'default')
    except ValueError:
        fl, fsrc = 1, 'default'
    h = None if fsrc == 'default' else h
    return {'id': p.get('id'), 'class': cls, 'classConfidence': conf, 'classSource': src,
            'footprintM2': round(area, 1), 'perimeterM': round(per, 1), 'heightM': h, 'floors': fl,
            'floorsSource': fsrc, 'floorAreaM2': round(area * fl, 1), 'centroid': [round(c[0], 7), round(c[1], 7)],
            'name': p.get('name') if cls not in ('residential', 'annex') else None}


# -------------------------------------------------------- compound grouping

PARAMS = {'annex_m2': 30.0, 'attach_m': 6.0, 'enclosure_max_m2': 6000.0}


def group_compounds(buildings, barriers, params=PARAMS):
    """Group footprints into compounds. Returns a list of compounds:
    {'structures': [profile...], 'rule', 'confidence', 'gates': [[lon, lat]...], 'plotM2'}."""
    profs = [profile(f) for f in buildings]
    rings = [_rings(f['geometry'])[0][0] for f in buildings]
    parent = list(range(len(profs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    rule = ['single'] * len(profs)
    encl = []
    gates = []
    for f in barriers:
        g = f['geometry']
        kind = (f.get('properties') or {}).get('barrier')
        if g['type'] == 'Point':
            if kind in ('gate', 'lift_gate', 'swing_gate', 'sliding_gate', 'entrance'):
                gates.append(g['coordinates'])
            continue
        if kind not in ('wall', 'fence', 'hedge'):
            continue
        if g['type'] == 'LineString':
            rs = [g['coordinates']]
        elif g['type'] in ('Polygon', 'MultiPolygon'):
            rs = [poly[0] for poly in _rings(g)]
        else:
            rs = []
        for r in rs:
            if len(r) >= 4 and r[0] == r[-1]:
                a, _, _ = ring_metrics(r)
                if 30 <= a <= params['enclosure_max_m2']:
                    encl.append((a, r))
    encl.sort(key=lambda e: e[0])
    member = {}
    for i, p in enumerate(profs):
        x, y = p['centroid']
        for a, r in encl:
            if _in_ring(x, y, r):
                member[i] = (a, id(r), r)
                break
    by_e = {}
    for i, (a, rid, r) in member.items():
        by_e.setdefault(rid, []).append(i)
    plot = {}
    for rid, ms in by_e.items():
        for m in ms[1:]:
            parent[find(m)] = find(ms[0])
        for m in ms:
            rule[m] = 'enclosure'
        plot[find(ms[0])] = member[ms[0]]
    for i, p in enumerate(profs):
        if rule[i] != 'single' or p['footprintM2'] >= params['annex_m2']:
            continue
        best = None
        for j, q in enumerate(profs):
            if j == i or q['footprintM2'] < params['annex_m2']:
                continue
            if abs(q['centroid'][0] - p['centroid'][0]) > 0.0004 or abs(q['centroid'][1] - p['centroid'][1]) > 0.0004:
                continue
            g = gap_m(rings[i], rings[j])
            if g <= params['attach_m'] and (best is None or g < best[0]):
                best = (g, j)
        if best:
            parent[find(i)] = find(best[1])
            rule[i] = 'annex'
            if rule[best[1]] == 'single':
                rule[best[1]] = 'annex-host'
    groups = {}
    for i in range(len(profs)):
        groups.setdefault(find(i), []).append(i)
    conf = {'enclosure': 0.85, 'annex': 0.6, 'annex-host': 0.6, 'single': 0.4}
    out = []
    for root, ms in groups.items():
        ms.sort(key=lambda m: -profs[m]['footprintM2'])  # structure 1 = the largest (main house)
        r = max((rule[m] for m in ms), key=lambda x: conf[x])
        enc = plot.get(root)
        cx = sum(profs[m]['centroid'][0] * profs[m]['footprintM2'] for m in ms) / max(1e-9, sum(profs[m]['footprintM2'] for m in ms))
        cy = sum(profs[m]['centroid'][1] * profs[m]['footprintM2'] for m in ms) / max(1e-9, sum(profs[m]['footprintM2'] for m in ms))
        gs = [g for g in gates if enc and _on_or_near_ring(g, enc[2], 2.0)]
        out.append({'structures': [profs[m] for m in ms], 'rule': r, 'confidence': conf[r],
                    'centroid': [round(cx, 7), round(cy, 7)], 'gates': gs,
                    'plotM2': round(enc[0], 1) if enc else None,
                    'floorAreaM2': round(sum(profs[m]['floorAreaM2'] for m in ms), 1),
                    'class': compound_class([profs[m] for m in ms])})
    return out


def _on_or_near_ring(pt, ring, tol_m):
    kx, ky = _local(pt[1])
    p = (pt[0] * kx, pt[1] * ky)
    rr = [(x * kx, y * ky) for x, y in ring]
    return min(_seg_dist(p, rr[i], rr[(i + 1) % len(rr)]) for i in range(len(rr))) <= tol_m


def compound_class(structs):
    dw = [s for s in structs if s['class'] == 'residential' and s['footprintM2'] >= PARAMS['annex_m2']]
    com = [s for s in structs if s['class'] in ('commercial', 'office', 'hospitality')]
    inst = [s for s in structs if s['class'] in ('education', 'health', 'religious', 'government')]
    if inst:
        return 'institutional'
    if dw and com:
        return 'mixed'
    if com:
        return 'commercial'
    if any(s['class'] == 'industrial' for s in structs) and not dw:
        return 'industrial'
    if dw:
        if any(s['floors'] >= 3 for s in dw):
            return 'residential-multi-storey'
        return 'residential-multi-household' if len(dw) >= 2 else 'residential-one-household'
    return 'unclassified'


# ------------------------------------------------ production grouping (registry)
# The rules of group_compounds at country scale, one code area at a time (SPEC 4 step 3).
# Hut clusters only in the rural communes of Alibori, Atacora, Borgou and Collines (not Parakou).

URBAN = {'annex_m2': 30.0, 'attach_m': 6.0, 'hut_m2': 0.0}
RURAL_NORTH = {'annex_m2': 30.0, 'attach_m': 6.0, 'hut_m2': 40.0, 'hut_gap_m': 3.0, 'hut_max': 25}
HUT_DEPARTEMENTS = ('Alibori', 'Atacora', 'Borgou', 'Collines')
HUT_EXCLUDED_COMMUNES = ('PKO',)


def grouping_params(commune):
    """Grouping parameters of a commune: hut clusters in the rural north and Collines."""
    c = keys()['_com'][commune]
    if c['departement'] in HUT_DEPARTEMENTS and commune not in HUT_EXCLUDED_COMMUNES:
        return RURAL_NORTH
    return URBAN


def _metres(lat0):
    p = math.radians(lat0)
    return 111132.92 - 559.82 * math.cos(2 * p) + 1.175 * math.cos(4 * p), 111412.84 * math.cos(p) - 93.5 * math.cos(3 * p)


def _plane(poly, lat0, lon0):
    m_lat, m_lon = _metres(lat0)
    return [((x - lon0) * m_lon, (y - lat0) * m_lat) for x, y in poly]


def _gap_plane(pa, pb):
    """Smallest distance in metres between two closed outlines in local metres (0 if they touch or overlap)."""
    if any(_in_ring(x, y, pb) for x, y in pa) or any(_in_ring(x, y, pa) for x, y in pb):
        return 0.0
    d = min(_seg_dist(q, pb[i], pb[i + 1]) for q in pa for i in range(len(pb) - 1))
    return min(d, min(_seg_dist(q, pa[i], pa[i + 1]) for q in pb for i in range(len(pa) - 1)))


def group_footprints(fs, params=URBAN):
    """Production grouping of one code area.

    fs: dicts with id (stable structure id), ring ([lon, lat] closed), area (m2), eid (the smallest
    closed enclosure of at most 6,000 m2 holding the centre, or None). Footprints are taken in id order,
    neighbours found on a 40 m grid, so the result never depends on the data's order. Rules, in order:
      enclosure    every footprint inside one enclosure is one compound;
      annex        a footprint under annex_m2 joins the nearest footprint of at least annex_m2 within
                   attach_m, outline to outline (only annexes join, and only to a building);
      hut-cluster  (rural north and Collines) huts under hut_m2 that belong to no house chain within
                   hut_gap_m, at most hut_max per compound: a cluster never joins two houses;
      single       everything else.
    Returns [(member indexes largest first, rule)] sorted by the main footprint's id."""
    if not fs:
        return []
    lat0 = sum(f['ring'][0][1] for f in fs) / len(fs)
    lon0 = sum(f['ring'][0][0] for f in fs) / len(fs)
    order = sorted(range(len(fs)), key=lambda i: fs[i]['id'])
    pts = [_plane(f['ring'], lat0, lon0) for f in fs]
    cent = [(sum(p[0] for p in q[:-1]) / max(1, len(q) - 1), sum(p[1] for p in q[:-1]) / max(1, len(q) - 1)) for q in pts]
    parent = list(range(len(fs)))
    rule = ['single'] * len(fs)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    first_in = {}
    for i in order:
        e = fs[i].get('eid')
        if e:
            r = first_in.setdefault(e, i)
            parent[find(i)] = find(r)
            rule[i] = 'enclosure'
    CELL = 40.0
    grid = {}
    for i in order:
        grid.setdefault((int(cent[i][0] // CELL), int(cent[i][1] // CELL)), []).append(i)

    def around(i, reach):
        cx, cy = int(cent[i][0] // CELL), int(cent[i][1] // CELL)
        k = int(reach // CELL) + 2
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    if j != i and math.dist(cent[i], cent[j]) <= 60:
                        yield j
    for i in order:
        if rule[i] != 'single' or fs[i]['area'] >= params['annex_m2']:
            continue
        best = None
        for j in around(i, params['attach_m']):
            if fs[j]['area'] < params['annex_m2']:
                continue
            g = _gap_plane(pts[i], pts[j])
            if g <= params['attach_m'] and (best is None or (g, fs[j]['id']) < (best[0], fs[best[1]]['id'])):
                best = (g, j)
        if best:
            parent[find(i)] = find(best[1])
            rule[i] = 'annex'
            if rule[best[1]] == 'single':
                rule[best[1]] = 'annex'
    if params.get('hut_m2'):
        size = {}
        for i in range(len(fs)):
            size[find(i)] = size.get(find(i), 0) + 1
        for i in order:
            if fs[i]['area'] >= params['hut_m2'] or rule[i] not in ('single', 'hut-cluster'):
                continue
            for j in sorted(around(i, params['hut_gap_m']), key=lambda j: fs[j]['id']):
                if fs[j]['area'] >= params['hut_m2'] or rule[j] not in ('single', 'hut-cluster'):
                    continue
                if _gap_plane(pts[i], pts[j]) > params['hut_gap_m']:
                    continue
                ri, rj = find(i), find(j)
                if ri != rj and size[ri] + size[rj] <= params['hut_max']:
                    parent[rj] = ri
                    size[ri] += size[rj]
                    rule[i] = rule[j] = 'hut-cluster'
    groups = {}
    for i in order:
        groups.setdefault(find(i), []).append(i)
    conf = {'enclosure': 0.85, 'annex': 0.6, 'hut-cluster': 0.5, 'single': 0.4}
    out = []
    for ms in groups.values():
        ms.sort(key=lambda i: (-fs[i]['area'], fs[i]['id']))
        out.append((ms, max((rule[m] for m in ms), key=lambda x: conf[x])))
    return sorted(out, key=lambda g: fs[g[0][0]]['id'])


# ------------------------------------------------------------ numbering

def hilbert_d(order, x, y):
    """Distance along a Hilbert curve of side 2**order for integer cell (x, y)."""
    n = 1 << order
    d = 0
    s = n >> 1
    while s > 0:
        rx = 1 if (x & s) else 0
        ry = 1 if (y & s) else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x, y = n - 1 - x, n - 1 - y
            x, y = y, x
        s >>= 1
    return d


def number_range(digits):
    lo = 10 ** (digits - 1)
    return lo, 10 ** digits - 1


def hilbert_key(box, lon, lat, order=16):
    x0, y0, x1, y1 = box
    n = (1 << order) - 1
    x = min(n, max(0, int((lon - x0) / max(1e-12, x1 - x0) * n)))
    y = min(n, max(0, int((lat - y0) / max(1e-12, y1 - y0) * n)))
    return hilbert_d(order, x, y)


def assign_numbers(points, box, block=(1000, 9000)):
    """Numbers for compounds (list of (id, lon, lat)) in one code area, inside the
    area's block (first, size) of its name's national range. Returns {id: number}.
    Main part = first two thirds of the block, step s; the top third is the tail reserve."""
    first, size = block
    main = (size * 2) // 3
    n = len(points)
    if n * 2 > size:
        raise ValueError(f'{n} compounds do not fit a block of {size} with headroom: take an extension block')
    step = max(1, main // max(1, n))
    order = sorted(points, key=lambda p: hilbert_key(box, p[1], p[2]))
    return {pid: first + i * step for i, (pid, _, _) in enumerate(order)}


def provisional_number(existing, box, lon, lat, block=(1000, 9000), retired=()):
    """Number for a new compound: a free number between its Hilbert neighbours,
    closest to their midpoint; else the lowest free number in the block's tail
    reserve. existing: {number: (lon, lat)}. A full block is extended with
    next_block() from the name's spare space."""
    first, size = block
    hi = first + size - 1
    tail0 = first + (size * 2) // 3
    taken = set(existing) | set(retired)
    k = hilbert_key(box, lon, lat)
    seq = sorted((hilbert_key(box, x, y), num) for num, (x, y) in existing.items() if first <= num < tail0)
    before = max((num for hk, num in seq if hk <= k), default=first - 1)
    after = min((num for hk, num in seq if hk > k), default=tail0)
    mid = (before + after) / 2
    free = [v for v in range(before + 1, after) if v not in taken]
    if free:
        return min(free, key=lambda v: (abs(v - mid), v))
    for v in range(tail0, hi + 1):
        if v not in taken:
            return v
    raise ValueError('block full: extend it from the name\'s spare space (next_block)')


# ------------------------------------------------------------------ demo

def number_by_area(comps):
    """Number compounds area by area, each inside its first block of the national
    name table. Returns {compound index: (area dict, number)}. The box of each area
    is the bounding box of its compounds here; the registry uses the frozen outline
    of the code area instead."""
    areas = {}
    for i, c in enumerate(comps):
        a = code_area(c['centroid'][1], c['centroid'][0])
        k = (a['commune'], a['arrondissement'], a['quartier'])
        areas.setdefault(k, (a, []))[1].append((i, c['centroid'][0], c['centroid'][1]))
    out = {}
    for k, (a, pts) in areas.items():
        xs = [p[1] for p in pts]
        ys = [p[2] for p in pts]
        box = (min(xs), min(ys), max(xs), max(ys))
        _, blocks = area_blocks(*k)
        for i, num in assign_numbers(pts, box, blocks[0]).items():
            out[i] = (a, num)
    return out


def demo():
    td = os.path.join(HERE, 'testdata')
    b = _load(os.path.join(td, 'cotonou-sample-buildings.geojson'))['features']
    w = _load(os.path.join(td, 'cotonou-sample-barriers.geojson'))['features']
    comps = group_compounds(b, w)
    return comps, number_by_area(comps)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == 'spot':
        print(json.dumps(spot_encode(float(argv[2]), float(argv[3])), ensure_ascii=False))
    elif cmd == 'unspot':
        print('%.7f %.7f' % spot_decode(' '.join(argv[2:])))
    elif cmd == 'area':
        print(json.dumps(code_area(float(argv[2]), float(argv[3])), ensure_ascii=False))
    elif cmd == 'check':
        print(damm(argv[2]))
    elif cmd == 'find':
        print(json.dumps(decode_remembered(' '.join(argv[2:])), ensure_ascii=False))
    elif cmd == 'parse':
        print(json.dumps(parse_machine(argv[2])))
    elif cmd == 'demo':
        comps, nums = demo()
        sizes = {}
        for c in comps:
            sizes[len(c['structures'])] = sizes.get(len(c['structures']), 0) + 1
        print(json.dumps({'structures': sum(len(c['structures']) for c in comps), 'compounds': len(comps),
                          'structuresPerCompound': sizes,
                          'areas': len({(a['commune'], a['arrondissement'], a['quartier']) for a, _ in nums.values()})},
                         ensure_ascii=False))
    else:
        print(__doc__)
        return 1
    return 0


def _cli(argv):
    try:
        return main(argv)
    except (ValueError, IndexError) as e:
        # A refused code is an answer, not a crash: print the reason only.
        print('refused: %s' % e, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(_cli(sys.argv))
