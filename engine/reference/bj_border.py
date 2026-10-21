"""Benin's national border: no Benin code for a building beyond it (engine/SPEC.md 1b).

A code is only ever issued for a building whose entrance lies inside Benin's national
border (OpenStreetMap's admin_level 2 boundary) or within BORDER_M of it. Arrondissement
outlines and spot frames reach over the border; they never decide.

engine/data/border.json is the boundary simplified to `toleranceM` (every point of the
full boundary lies within that distance of the simplified one, and the other way round).
check() and abroad() take that into account: on the shipped outline a point is refused
when it lies more than BORDER_M - toleranceM outside it, so nothing more than BORDER_M
outside the full border is ever accepted, and nothing inside the full border or within
BORDER_M - 2 x toleranceM of it is ever refused. tools/country-border.py writes the file
and checks the bound; the pipeline (tools/issue_registry.py) uses the full boundary of the
work folder with no margin.

Distances are on the local plane: 110,574 m per degree of latitude, 111,320 m per degree of
longitude times the cosine of the point's latitude. Standard library only.
"""
import json
import math
import os

BORDER_M = 300.0
M_LAT = 110574.0
M_LON = 111320.0
CELL = 0.01            # degrees: the side of the index cells
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'border.json')


def rings_of(geometry):
    """Every ring (outer and holes) of a GeoJSON Polygon or MultiPolygon, as (lon, lat) lists."""
    t, c = geometry['type'], geometry['coordinates']
    polys = [c] if t == 'Polygon' else c if t == 'MultiPolygon' else []
    return [[(float(p[0]), float(p[1])) for p in ring] for poly in polys for ring in poly]


class Border(object):
    """A national border: point-in-border and distance outside it, on a 0.01 degree index."""

    def __init__(self, rings, tolerance_m=0.0):
        self.tolerance_m = float(tolerance_m)
        self.segs = []
        for ring in rings:
            pts = list(ring)
            if pts and pts[0] != pts[-1]:
                pts.append(pts[0])
            for i in range(len(pts) - 1):
                (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                if (x1, y1) != (x2, y2):
                    self.segs.append((x1, y1, x2, y2))
        self.bands, self.cells = {}, {}
        for k, (x1, y1, x2, y2) in enumerate(self.segs):
            for b in range(int(math.floor(min(y1, y2) / CELL)), int(math.floor(max(y1, y2) / CELL)) + 1):
                self.bands.setdefault(b, []).append(k)
            for cx in range(int(math.floor(min(x1, x2) / CELL)), int(math.floor(max(x1, x2) / CELL)) + 1):
                for cy in range(int(math.floor(min(y1, y2) / CELL)), int(math.floor(max(y1, y2) / CELL)) + 1):
                    self.cells.setdefault((cx, cy), []).append(k)

    @classmethod
    def load(cls, path=DATA):
        """The shipped outline (engine/data/border.json), or a GeoJSON file of the full
        boundary (a FeatureCollection, a Feature or a geometry; tolerance 0)."""
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
        if 'polygons' in d:
            return cls([r for poly in d['polygons'] for r in poly], d['toleranceM'])
        feats = d['features'] if d.get('type') == 'FeatureCollection' else [d]
        rings = []
        for f in feats:
            rings += rings_of(f.get('geometry', f))
        return cls(rings, 0.0)

    def contains(self, lat, lon):
        """Ray casting over every ring (even-odd), with only the segments of the point's band."""
        inside = False
        for k in self.bands.get(int(math.floor(lat / CELL)), ()):
            x1, y1, x2, y2 = self.segs[k]
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                inside = not inside
        return inside

    def _seg_m(self, lat, lon, k):
        x1, y1, x2, y2 = self.segs[k]
        c = math.cos(math.radians(lat)) * M_LON
        ax, ay = (x1 - lon) * c, (y1 - lat) * M_LAT
        vx, vy = (x2 - x1) * c, (y2 - y1) * M_LAT
        ll = vx * vx + vy * vy
        t = 0.0 if ll == 0 else min(1.0, max(0.0, -(ax * vx + ay * vy) / ll))
        return math.hypot(ax + t * vx, ay + t * vy)

    def edge_m(self, lat, lon, within=None):
        """Distance in metres to the nearest segment; with `within`, only segments of the
        cells that can hold one that near are searched (math.inf when none is)."""
        if within is None:
            ks = range(len(self.segs))
        else:
            ry = int(math.ceil(within / M_LAT / CELL))
            rx = int(math.ceil(within / (M_LON * max(0.1, math.cos(math.radians(abs(lat) + 1)))) / CELL))
            cx, cy = int(math.floor(lon / CELL)), int(math.floor(lat / CELL))
            ks = set()
            for i in range(cx - rx, cx + rx + 1):
                for j in range(cy - ry, cy + ry + 1):
                    ks.update(self.cells.get((i, j), ()))
        return min((self._seg_m(lat, lon, k) for k in ks), default=math.inf)

    def outside_m(self, lat, lon):
        """0 inside the border, else the distance to it in metres."""
        return 0.0 if self.contains(lat, lon) else self.edge_m(lat, lon)

    def beyond(self, lat, lon, m=BORDER_M):
        """The point lies more than m metres outside this outline."""
        return not self.contains(lat, lon) and self.edge_m(lat, lon, within=m) > m

    def abroad(self, lat, lon, m=BORDER_M):
        """The point lies more than m metres outside the full border, as far as this outline
        can tell: beyond m - toleranceM of it (section 1b)."""
        return self.beyond(lat, lon, m - self.tolerance_m)


_border = None


def border():
    global _border
    if _border is None:
        _border = Border.load()
    return _border


def abroad(lat, lon):
    """The point is more than 300 m outside Benin's national border: it can have no Benin code."""
    return border().abroad(lat, lon)
