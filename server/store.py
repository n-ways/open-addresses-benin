"""The SQLite store: import of the published registry, export in the same format,
and the queries the API needs.

The 22 registry columns are kept as the exact text of the published files, so an
export of an imported registry is byte-identical to it. Typed copies of the
columns the queries need (number, coordinates, keys) sit beside them.
"""
import contextlib
import csv
import datetime
import gzip
import hashlib
import io
import json
import math
import os
import queue
import sqlite3
import threading
import time

from . import COUNTRY, CREDIT
from . import engine as X

CODE_COLUMNS = ['machine', 'home', 'written', 'zone', 'official_name', 'number', 'check', 'status', 'issued', 'issued_at',
                'entrance_lat', 'entrance_lng', 'entrance_kind', 'spot_code', 'official_address', 'class', 'use', 'kind',
                'structures', 'floor_area_m2', 'rule', 'estate']
AREA_COLUMNS = ['zone', 'id', 'plate_name', 'official_name', 'commune', 'arrondissement', 'departement', 'name_key',
                'name_index', 'digits', 'blocks', 'provisional_name', 'place_lat', 'place_lon', 'frame']
ENGINE = 'internal/addressing/bj (SPEC v1.0)'
LICENCE = 'ODbL 1.0 (LICENSE-DATA)'
GRID = 1000  # cells per degree of the fallback spatial index (about 110 m)


class ImportError_(Exception):
    """The registry does not match its manifest; nothing was changed."""


def q(c):
    return '"%s"' % c


def now_rfc3339():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ------------------------------------------------------------------ CSV in the published dialect

def _needs_quotes(field):
    if field == '':
        return False
    if field == '\\.':
        return True
    if any(c in field for c in '\n\r",'):
        return True
    return field[0].isspace()


def csv_line(fields):
    """One CSV record exactly as the published files write it (RFC 4180 quoting only
    where needed, LF line ends)."""
    out = []
    for f in fields:
        if _needs_quotes(f):
            out.append('"' + f.replace('"', '""') + '"')
        else:
            out.append(f)
    return ','.join(out) + '\n'


class _HashingLines(object):
    """Lines of a gzip file, decoded, while the SHA-256 of its uncompressed bytes is taken."""

    def __init__(self, path):
        self.path = path
        self.sha = hashlib.sha256()

    def __iter__(self):
        with gzip.open(self.path, 'rb') as fh:
            for raw in fh:
                self.sha.update(raw)
                yield raw.decode('utf-8')


# ------------------------------------------------------------------ the database

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS areas (
  zone TEXT PRIMARY KEY, id INTEGER NOT NULL UNIQUE, plate_name TEXT, official_name TEXT, commune TEXT,
  arrondissement TEXT, departement TEXT, name_key TEXT, name_index INTEGER, digits INTEGER, blocks TEXT,
  provisional_name TEXT, place_lat TEXT, place_lon TEXT, frame TEXT,
  unit TEXT NOT NULL, plate_key TEXT NOT NULL, official_key TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS areas_unit ON areas (unit);
CREATE INDEX IF NOT EXISTS areas_plate_key ON areas (plate_key);
CREATE INDEX IF NOT EXISTS areas_official_key ON areas (official_key);
CREATE TABLE IF NOT EXISTS local_blocks (zone TEXT NOT NULL, lo INTEGER NOT NULL, hi INTEGER NOT NULL, added_at TEXT NOT NULL,
  PRIMARY KEY (zone, lo));
CREATE TABLE IF NOT EXISTS codes (
  id INTEGER PRIMARY KEY, unit TEXT NOT NULL, source TEXT NOT NULL,
  %s,
  name_index INTEGER NOT NULL, num INTEGER NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL,
  anchor_lat REAL NOT NULL, anchor_lng REAL NOT NULL, official_key TEXT, outline TEXT, grid INTEGER);
CREATE TABLE IF NOT EXISTS issue_log (key_id TEXT NOT NULL, machine TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS issue_log_key ON issue_log (key_id, at);
CREATE TABLE IF NOT EXISTS changes (machine TEXT NOT NULL, at TEXT NOT NULL, key_id TEXT, field TEXT NOT NULL,
  before TEXT, after TEXT);
""" % ',\n  '.join('%s TEXT NOT NULL' % q(c) for c in CODE_COLUMNS)

CODE_INDEXES = [
    'CREATE UNIQUE INDEX IF NOT EXISTS codes_machine ON codes (machine)',
    'CREATE UNIQUE INDEX IF NOT EXISTS codes_name_number ON codes (name_index, num)',
    'CREATE INDEX IF NOT EXISTS codes_home ON codes (home)',
    'CREATE INDEX IF NOT EXISTS codes_official ON codes (official_key) WHERE official_key IS NOT NULL',
    'CREATE INDEX IF NOT EXISTS codes_zone ON codes (zone, machine)',
    'CREATE INDEX IF NOT EXISTS codes_unit ON codes (unit, name_index, num)',
    'CREATE INDEX IF NOT EXISTS codes_number ON codes (num)',
    'CREATE INDEX IF NOT EXISTS codes_grid ON codes (grid)',
]


def has_rtree(conn):
    try:
        conn.execute('CREATE VIRTUAL TABLE IF NOT EXISTS temp.rtree_probe USING rtree(id, a, b, c, d)')
        conn.execute('DROP TABLE temp.rtree_probe')
        return True
    except sqlite3.OperationalError:
        return False


def grid_cell(lat, lng):
    return int(math.floor(lat * GRID)) * 1000000 + int(math.floor(lng * GRID)) + 500000


def connect(path, readonly=False):
    if readonly:
        conn = sqlite3.connect('file:%s?mode=ro' % path, uri=True, check_same_thread=False, timeout=30)
    else:
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, timeout=30, isolation_level=None)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    rtree = has_rtree(conn)
    if rtree:
        conn.execute('CREATE VIRTUAL TABLE IF NOT EXISTS codes_rtree USING rtree(id, min_lat, max_lat, min_lng, max_lng)')
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('spatial', ?)", ('rtree' if rtree else 'grid',))
    for s in CODE_INDEXES:
        conn.execute(s)


def meta(conn, key, default=None):
    r = conn.execute('SELECT value FROM meta WHERE key = ?', (key,)).fetchone()
    return r[0] if r else default


def set_meta(conn, key, value):
    conn.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', (key, value))


def area_record(row):
    """The areas-table values of an areas.csv record."""
    return [row[c] for c in AREA_COLUMNS] + [row['zone'][:3], X.norm_name(row['plate_name']), X.norm_name(row['official_name'])]


def code_values(unit, source, row, name_index, anchor=None, outline=None):
    """The codes-table values of a registry record: its columns as text, then the typed copies."""
    lat, lng = float(row['entrance_lat']), float(row['entrance_lng'])
    alat, alng = anchor if anchor else (lat, lng)
    off = row['official_address']
    return [unit, source] + [row[c] for c in CODE_COLUMNS] + [name_index, int(row['number']), lat, lng, alat, alng,
                                                              X.norm_address(off) if off else None, outline,
                                                              grid_cell(lat, lng)]


# ------------------------------------------------------------------ import

def import_registry(db_path, registry_dir, force=False, log=print):
    """Load registry_dir into db_path. Every file is checked against MANIFEST.json
    (SHA-256 of the uncompressed bytes, rows per file, total); on any mismatch the
    database is left as it was. Codes this deployment issued itself are kept unless
    the registry now holds the same code or number."""
    man_path = os.path.join(registry_dir, 'MANIFEST.json')
    with open(man_path, 'rb') as fh:
        man_bytes = fh.read()
    man = json.loads(man_bytes.decode('utf-8'))
    if man.get('country') != COUNTRY:
        raise ImportError_('MANIFEST.json is for country %r, not %s' % (man.get('country'), COUNTRY))
    shas = man.get('sha256', {})
    present = sorted(f[:-3] for f in os.listdir(registry_dir) if f.endswith('.csv.gz'))
    if sorted(shas) != present:
        raise ImportError_('the files in %s do not match MANIFEST.json: missing %s, unlisted %s'
                           % (registry_dir, sorted(set(shas) - set(present)), sorted(set(present) - set(shas))))
    if 'areas.csv' not in shas:
        raise ImportError_('MANIFEST.json lists no areas.csv')
    units = sorted(f[:-4] for f in present if f != 'areas.csv')
    if sorted(man.get('byUnit', {})) != units:
        raise ImportError_('MANIFEST.json byUnit does not list the same files as sha256')
    man_sha = hashlib.sha256(man_bytes).hexdigest()

    conn = connect(db_path)
    init_schema(conn)
    if not force and meta(conn, 'manifest_sha256') == man_sha and meta(conn, 'import_complete') == '1':
        n = conn.execute("SELECT count(*) FROM codes WHERE source = 'registry'").fetchone()[0]
        if n == man['codes']:
            log('registry already imported (%d codes); nothing to do' % n)
            conn.close()
            return n
    rtree = meta(conn, 'spatial') == 'rtree'
    conn.execute('PRAGMA cache_size = -262144')
    t0 = time.time()
    conn.execute('BEGIN IMMEDIATE')
    try:
        # Areas.
        lines = _HashingLines(os.path.join(registry_dir, 'areas.csv.gz'))
        rd = csv.reader(lines)
        header = next(rd)
        if header != AREA_COLUMNS:
            raise ImportError_('areas.csv has columns %s, expected %s' % (header, AREA_COLUMNS))
        conn.execute('DELETE FROM areas')
        n_areas = 0
        for rec in rd:
            row = dict(zip(AREA_COLUMNS, rec))
            conn.execute('INSERT INTO areas VALUES (%s)' % ','.join('?' * (len(AREA_COLUMNS) + 3)), area_record(row))
            n_areas += 1
        if lines.sha.hexdigest() != shas['areas.csv']:
            raise ImportError_('areas.csv: SHA-256 %s does not match MANIFEST.json %s' % (lines.sha.hexdigest(), shas['areas.csv']))
        name_index = {r[0]: r[1] for r in conn.execute('SELECT zone, name_index FROM areas')}

        # Codes this deployment issued: set aside, put back after the registry.
        local = conn.execute("SELECT * FROM codes WHERE source = 'local'").fetchall()
        for s in CODE_INDEXES:
            conn.execute('DROP INDEX IF EXISTS %s' % s.split(' ON ')[0].split()[-1])
        conn.execute('DELETE FROM codes')
        if rtree:
            conn.execute('DELETE FROM codes_rtree')
        cols = ['unit', 'source'] + CODE_COLUMNS + ['name_index', 'num', 'lat', 'lng', 'anchor_lat', 'anchor_lng',
                                                    'official_key', 'outline', 'grid']
        ins = 'INSERT INTO codes (%s) VALUES (%s)' % (','.join(q(c) for c in cols), ','.join('?' * len(cols)))
        total = 0
        for unit in units:
            lines = _HashingLines(os.path.join(registry_dir, unit + '.csv.gz'))
            rd = csv.reader(lines)
            header = next(rd)
            if header != CODE_COLUMNS:
                raise ImportError_('%s.csv has columns %s, expected %s' % (unit, header, CODE_COLUMNS))
            count = 0
            batch = []
            for rec in rd:
                row = dict(zip(CODE_COLUMNS, rec))
                if row['zone'] not in name_index:
                    raise ImportError_('%s.csv: %s is in area %s, which areas.csv does not list' % (unit, row['machine'], row['zone']))
                batch.append(code_values(unit, 'registry', row, name_index[row['zone']]))
                count += 1
                if len(batch) >= 20000:
                    conn.executemany(ins, batch)
                    batch = []
            if batch:
                conn.executemany(ins, batch)
            got = lines.sha.hexdigest()
            if got != shas[unit + '.csv']:
                raise ImportError_('%s.csv: SHA-256 %s does not match MANIFEST.json %s' % (unit, got, shas[unit + '.csv']))
            if count != man['byUnit'][unit]:
                raise ImportError_('%s.csv: %d codes, MANIFEST.json says %d' % (unit, count, man['byUnit'][unit]))
            total += count
            log('  %s.csv  %8d codes  sha256 ok' % (unit, count))
        if total != man['codes']:
            raise ImportError_('%d codes in the files, MANIFEST.json says %d' % (total, man['codes']))

        # Codes issued here, unless the registry now has them.
        kept = dropped = 0
        if local:
            names = local[0].keys()
            for r in local:
                v = dict(zip(names, r))
                v.pop('id')
                try:
                    conn.execute('INSERT INTO codes (%s) VALUES (%s)' % (','.join(q(c) for c in v), ','.join('?' * len(v))),
                                 list(v.values()))
                    kept += 1
                except sqlite3.IntegrityError:
                    dropped += 1
        log('  building indexes')
        for s in CODE_INDEXES:
            conn.execute(s)
        # A local code whose number the registry now holds: the registry wins.
        dup = conn.execute("""SELECT l.id FROM codes l JOIN codes r ON r.name_index = l.name_index AND r.num = l.num
                              AND r.source = 'registry' WHERE l.source = 'local'""").fetchall()
        for (i,) in dup:
            conn.execute('DELETE FROM codes WHERE id = ?', (i,))
        dropped += len(dup)
        kept -= len(dup)
        if rtree:
            log('  building the spatial index')
            conn.execute('INSERT INTO codes_rtree SELECT id, lat, lat, lng, lng FROM codes')
        set_meta(conn, 'manifest', man_bytes.decode('utf-8'))
        set_meta(conn, 'manifest_sha256', man_sha)
        set_meta(conn, 'exported', man.get('exported', ''))
        set_meta(conn, 'imported_at', now_rfc3339())
        set_meta(conn, 'country', COUNTRY)
        set_meta(conn, 'dirty', '1' if kept else '0')
        set_meta(conn, 'import_complete', '1')
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        conn.close()
        raise
    conn.execute('ANALYZE')
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    conn.close()
    log('imported %d codes in %d areas in %.0f s%s' % (total, n_areas, time.time() - t0,
                                                         ('; kept %d local codes, dropped %d' % (kept, dropped)) if local else ''))
    return total


# ------------------------------------------------------------------ export

def _gzip_write(path, chunks):
    """Write text chunks gzip-compressed with no name and no timestamp (as gzip -n);
    returns the SHA-256 of the uncompressed bytes."""
    h = hashlib.sha256()
    with open(path, 'wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as gz:
            buf = []
            size = 0
            for c in chunks:
                b = c.encode('utf-8')
                h.update(b)
                buf.append(b)
                size += len(b)
                if size > 1 << 20:
                    gz.write(b''.join(buf))
                    buf, size = [], 0
            if buf:
                gz.write(b''.join(buf))
    return h.hexdigest()


def export_registry(db_path, out_dir, log=print):
    """Write the registry in the published format: areas.csv.gz, one <commune>.csv.gz
    per commune, MANIFEST.json."""
    conn = connect(db_path, readonly=True)
    os.makedirs(out_dir, exist_ok=True)
    shas, counts = {}, {}
    areas = load_areas(conn)

    def area_lines():
        yield csv_line(AREA_COLUMNS)
        for r in conn.execute('SELECT * FROM areas ORDER BY rowid'):
            row = {c: r[c] for c in AREA_COLUMNS}
            row['blocks'] = areas.by_zone[r['zone']].blocks_text()
            yield csv_line([str(row[c]) for c in AREA_COLUMNS])
    shas['areas.csv'] = _gzip_write(os.path.join(out_dir, 'areas.csv.gz'), area_lines())

    units = [r[0] for r in conn.execute('SELECT DISTINCT unit FROM codes ORDER BY unit')]
    total = 0
    for unit in units:
        n = [0]

        def lines(unit=unit, n=n):
            yield csv_line(CODE_COLUMNS)
            for r in conn.execute('SELECT %s FROM codes WHERE unit = ? ORDER BY name_index, num' % ','.join(q(c) for c in CODE_COLUMNS),
                                  (unit,)):
                n[0] += 1
                yield csv_line(list(r))
        shas[unit + '.csv'] = _gzip_write(os.path.join(out_dir, unit + '.csv.gz'), lines())
        counts[unit] = n[0]
        total += n[0]
        log('  %s.csv  %8d codes' % (unit, n[0]))

    old = meta(conn, 'manifest')
    if old and meta(conn, 'dirty') == '0' and json.loads(old).get('sha256') == shas:
        text = old  # nothing changed since the import: the published manifest, as it was
    else:
        man = {'country': COUNTRY, 'engine': ENGINE, 'exported': now_rfc3339(), 'codes': total, 'byUnit': counts,
               'sha256': shas, 'credit': CREDIT, 'licence': LICENCE}
        text = json.dumps(man, indent=2, ensure_ascii=False, sort_keys=True) + '\n'
    with open(os.path.join(out_dir, 'MANIFEST.json'), 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)
    conn.close()
    log('exported %d codes to %s' % (total, out_dir))
    return total


# ------------------------------------------------------------------ queries

def load_areas(conn):
    extra = {}
    for r in conn.execute('SELECT zone, lo, hi FROM local_blocks ORDER BY rowid'):
        extra.setdefault(r[0], []).append((r[1], r[2]))
    out = []
    for r in conn.execute('SELECT * FROM areas ORDER BY rowid'):
        row = {c: str(r[c]) for c in AREA_COLUMNS}
        out.append(X.Area(row, extra.get(r['zone'], ())))
    return X.Register(out)


class Store(object):
    """The open database of a running server: one connection per thread, one writer at a time."""

    def __init__(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError('no database at %s: run "python3 -m server import" first' % path)
        self.path = path
        self.local = threading.local()
        self.write_lock = threading.Lock()
        self.pool = queue.LifoQueue()
        self.all = []
        with self.session() as c:
            if meta(c, 'import_complete') != '1':
                raise RuntimeError('the database at %s holds no complete import' % path)
            init_schema(c)
            self.rtree = meta(c, 'spatial') == 'rtree'
            self.register = load_areas(c)
            self.manifest = json.loads(meta(c, 'manifest'))

    @contextlib.contextmanager
    def session(self):
        """A pooled connection for the current thread for the length of one request."""
        try:
            c = self.pool.get_nowait()
        except queue.Empty:
            c = connect(self.path)
            self.all.append(c)
        self.local.c = c
        try:
            yield c
        finally:
            self.local.c = None
            self.pool.put(c)

    def conn(self):
        c = getattr(self.local, 'c', None)
        if c is None:
            raise RuntimeError('no database session on this thread')
        return c

    def close(self):
        for c in self.all:
            c.close()
        self.all = []

    # ---- reads

    def count(self, where='', args=()):
        return self.conn().execute('SELECT count(*) FROM codes ' + where, args).fetchone()[0]

    def by_machine(self, machine):
        return self.conn().execute('SELECT * FROM codes WHERE machine = ?', (machine,)).fetchone()

    def by_number(self, name_index, number):
        return self.conn().execute('SELECT * FROM codes WHERE name_index = ? AND num = ?', (name_index, number)).fetchone()

    def by_official(self, key, limit):
        c = self.conn()
        n = c.execute('SELECT count(*) FROM codes WHERE official_key = ?', (key,)).fetchone()[0]
        rows = c.execute('SELECT * FROM codes WHERE official_key = ? ORDER BY machine LIMIT ?', (key, limit)).fetchall()
        return n, rows

    def zone_numbers(self, zone):
        """(number, anchor lat, anchor lng) of every code ever issued in an area."""
        return [(r[0], r[1], r[2]) for r in
                self.conn().execute('SELECT num, anchor_lat, anchor_lng FROM codes WHERE zone = ?', (zone,))]

    def within(self, lat, lng, radius_m, include_retired=False):
        """Codes whose entrance is within radius_m of the point, nearest first:
        [(distance, row)], ties by machine code."""
        dlat = radius_m / 110574.0 + 1e-6
        dlng = radius_m / (111320.0 * max(0.2, math.cos(math.radians(lat)))) + 1e-6
        c = self.conn()
        if self.rtree:
            rows = c.execute("""SELECT codes.* FROM codes_rtree JOIN codes ON codes.id = codes_rtree.id
                WHERE min_lat <= ? AND max_lat >= ? AND min_lng <= ? AND max_lng >= ?""",
                             (lat + dlat, lat - dlat, lng + dlng, lng - dlng)).fetchall()
        else:
            cells = []
            for i in range(int(math.floor((lat - dlat) * GRID)), int(math.floor((lat + dlat) * GRID)) + 1):
                for j in range(int(math.floor((lng - dlng) * GRID)), int(math.floor((lng + dlng) * GRID)) + 1):
                    cells.append(i * 1000000 + j + 500000)
            rows = []
            for k in range(0, len(cells), 500):
                part = cells[k:k + 500]
                rows += c.execute('SELECT * FROM codes WHERE grid IN (%s)' % ','.join('?' * len(part)), part).fetchall()
        out = []
        for r in rows:
            if r['status'] == 'retired' and not include_retired:
                continue
            d = X.ground_m(lat, lng, r['lat'], r['lng'])
            if d <= radius_m:
                out.append((d, r))
        out.sort(key=lambda x: (x[0], x[1]['machine']))
        return out

    def code_at(self, lat, lng, max_m):
        """The code of the building a point is in (an outline recorded here holds it),
        else the nearest entrance within max_m; retired codes are never found."""
        cand = self.within(lat, lng, max(max_m, 60.0))
        for d, r in cand:
            if r['outline']:
                ring = json.loads(r['outline'])
                if X.ring_contains(ring, lng, lat):
                    return 0.0, r
        for d, r in cand:
            if d <= max_m:
                return d, r
        return None

    def overlapping(self, ring):
        """A code issued here whose recorded outline shares more than half of the smaller
        of the two outlines."""
        lat = sum(p[1] for p in ring) / len(ring)
        lng = sum(p[0] for p in ring) / len(ring)
        a2 = X.ring_area_m2(ring)
        for d, r in self.within(lat, lng, 150.0):
            if not r['outline']:
                continue
            other = json.loads(r['outline'])
            if X.ring_overlap_m2(ring, other) > 0.5 * min(a2, X.ring_area_m2(other)):
                return r
        return None

    def zone_page(self, unit, after, limit):
        return self.conn().execute('SELECT * FROM codes WHERE unit = ? AND machine > ? ORDER BY machine LIMIT ?',
                                   (unit, after, limit)).fetchall()

    def issued_by(self, key_id, since):
        return self.conn().execute('SELECT count(*) FROM issue_log WHERE key_id = ? AND at >= ?', (key_id, since)).fetchone()[0]

    # ---- writes (callers hold write_lock)

    def insert_local(self, row, unit, anchor, outline, new_blocks, key_id):
        c = self.conn()
        cols = ['unit', 'source'] + CODE_COLUMNS + ['name_index', 'num', 'lat', 'lng', 'anchor_lat', 'anchor_lng',
                                                    'official_key', 'outline', 'grid']
        a = self.register.by_zone[row['zone']]
        v = code_values(unit, 'local', row, a.name_index, anchor, outline)
        c.execute('BEGIN IMMEDIATE')
        try:
            for b in new_blocks:
                c.execute('INSERT INTO local_blocks (zone, lo, hi, added_at) VALUES (?, ?, ?, ?)', (row['zone'], b[0], b[1], row['issued_at']))
            cur = c.execute('INSERT INTO codes (%s) VALUES (%s)' % (','.join(q(x) for x in cols), ','.join('?' * len(cols))), v)
            if self.rtree:
                c.execute('INSERT INTO codes_rtree VALUES (?, ?, ?, ?, ?)', (cur.lastrowid, v[-7], v[-7], v[-6], v[-6]))
            c.execute('INSERT INTO issue_log (key_id, machine, at) VALUES (?, ?, ?)', (key_id, row['machine'], time.time()))
            set_meta(c, 'dirty', '1')
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK')
            raise
        for b in new_blocks:
            self.register.add_block(row['zone'], b)

    def update(self, machine, fields, key_id):
        """Change registry columns of one code; logs each change."""
        c = self.conn()
        old = self.by_machine(machine)
        c.execute('BEGIN IMMEDIATE')
        try:
            at = now_rfc3339()
            for k, v in fields.items():
                if k in CODE_COLUMNS and old[k] != v:
                    c.execute('INSERT INTO changes (machine, at, key_id, field, before, after) VALUES (?, ?, ?, ?, ?, ?)',
                              (machine, at, key_id, k, old[k], v))
            sets = ', '.join('%s = ?' % q(k) for k in fields)
            c.execute('UPDATE codes SET %s WHERE machine = ?' % sets, list(fields.values()) + [machine])
            if 'lat' in fields and self.rtree:
                c.execute('UPDATE codes_rtree SET min_lat = ?, max_lat = ?, min_lng = ?, max_lng = ? WHERE id = ?',
                          (fields['lat'], fields['lat'], fields['lng'], fields['lng'], old['id']))
            set_meta(c, 'dirty', '1')
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK')
            raise
        return self.by_machine(machine)
