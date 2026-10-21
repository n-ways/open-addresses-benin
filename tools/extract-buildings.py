#!/usr/bin/env python3
"""Extract every Beninese building footprint with its raw profile facts.

One DuckDB run (memory_limit 3GB, spilling to the work folder) over N-Ways' map
data, read-only:
  data/detail/countries/benin/buildings-src.geojsonseq  OpenStreetMap buildings (ODbL)
  data/detail/ml/BJ.parquet                                    Google Open Buildings / Microsoft footprints (CC BY 4.0 / ODbL)
plus the small inputs of tools/prepare-inputs.py in the work folder, among them the
national boundary (country.geojson) and the units (units.geojson).

The border decides (engine/SPEC.md 1b): only a footprint whose centre lies inside the national
boundary (country.geojson, OpenStreetMap admin_level 2) is kept, stricter than the issuer's 300 m;
a footprint over the border is in a neighbouring country and gets nothing, whatever the
arrondissement outlines (geoBoundaries) say. Every footprint kept gets:
  eid      the smallest closed wall, fence or hedge (<= 6,000 m2) holding its centre (SPEC 4, rule 1)
  estate   the larger enclosure, N-Ways estate, government, military or police compound holding it
  unit     its arrondissement (model/keys.json id)
  poi      the N-Ways places on it
  street   in Cotonou, the nearest named street within 30 m (its name and the code of the 2013 plan)

Writes <work>/buildings-raw.csv (one row per footprint, with a stable row id bid and its
outline as WKT) and <work>/buildings-pts.csv (bid, centre, unit and dens, the footprints in
its 100 m x 100 m cell, x = lon x 111,320 x cos 9.3 deg, y = lat x 110,574); tools/assign-areas.py then gives each its code area, and
tools/sort-buildings.py writes <work>/buildings.csv sorted by area.

  python3 tools/extract-buildings.py <work folder>
"""
import math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.environ.get('NWAYS_ROOT', os.path.dirname(os.path.dirname(REPO)))
work = os.path.abspath(sys.argv[1])
osm = os.path.join(ROOT, 'data', 'detail', 'countries', 'benin', 'buildings-src.geojsonseq')
ml = os.path.join(ROOT, 'data', 'detail', 'ml', 'BJ.parquet')
W = lambda f: os.path.join(work, f)

TAGS = ['building', 'amenity', 'shop', 'office', 'religion', 'tourism', 'healthcare', 'man_made',
        'government', 'craft', 'building:levels', 'height', 'name', 'roof:material', 'building:material']
tag_cols = ', '.join(f"json_extract_string(j, '$.properties.\"{t}\"') AS \"{t}\"" for t in TAGS)
null_cols = ', '.join(f"NULL::VARCHAR AS \"{t}\"" for t in TAGS)
KX = 111320.0 * math.cos(math.radians(9.3))
import json
COT = ','.join("'%s'" % a['id'] for a in json.load(open(os.path.join(REPO, 'model', 'keys.json'), encoding='utf-8'))['arrondissements'] if a['commune'] == 'COT')
area_m2 = "ST_Area(g) * 110574.0 * 111320.0 * cos(radians(ST_Y(ST_Centroid(g))))"

sql = f"""
SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false; SET temp_directory='{W('duck-tmp')}';
INSTALL spatial; LOAD spatial;
CREATE TABLE ol AS SELECT ST_Union_Agg(geom) AS geom FROM ST_Read('{W('country.geojson')}');
CREATE TABLE e AS SELECT eid, kind, areaM2, geom FROM ST_Read('{W('enclosures.geojson')}');
CREATE TABLE es AS SELECT estate, kind, geom FROM ST_Read('{W('estates.geojson')}');
CREATE TABLE lb AS SELECT unit, geom FROM ST_Read('{W('units.geojson')}');
CREATE TABLE p AS SELECT id, "name", category, ST_Point(lon, lat) AS g FROM read_csv('{W('places.csv')}', header=true,
  columns={{'id':'VARCHAR','name':'VARCHAR','category':'VARCHAR','source':'VARCHAR','lon':'DOUBLE','lat':'DOUBLE'}});
CREATE TABLE raw AS
  SELECT 'osm' AS src, json_extract_string(j, '$.properties."@type"') || '/' || json_extract_string(j, '$.properties."@id"') AS oid,
         ST_GeomFromGeoJSON(json_extract(j, '$.geometry')) AS g, {tag_cols}
  FROM (SELECT ltrim(line, chr(30)) AS j FROM read_csv('{osm}', columns={{'line':'VARCHAR'}}, header=false, delim=chr(1), quote='', escape='', max_line_size=16000000) WHERE length(line) > 2)
  UNION ALL
  SELECT 'ml', NULL, geometry, {null_cols} FROM '{ml}';
CREATE TABLE b AS SELECT row_number() OVER () AS bid, *, ST_Centroid(g) AS c, {area_m2} AS area,
  ST_Perimeter_Spheroid(ST_FlipCoordinates(g)) AS perim FROM raw;
DROP TABLE raw;
DELETE FROM b WHERE NOT ST_Contains((SELECT geom FROM ol), b.c);
CREATE TABLE be AS SELECT bid, arg_min(eid, areaM2) AS eid FROM (SELECT b.bid, e.eid, e.areaM2 FROM b JOIN e ON ST_Contains(e.geom, b.c)) GROUP BY bid;
CREATE TABLE bes AS SELECT b.bid, min(es.estate) AS estate FROM b JOIN es ON ST_Contains(es.geom, b.c) GROUP BY b.bid;
CREATE TABLE bl AS SELECT b.bid, min(lb.unit) AS unit FROM b JOIN lb ON ST_Contains(lb.geom, b.c) GROUP BY b.bid;
CREATE TABLE st AS SELECT sid, "name", ST_GeomFromText(wkt) AS g FROM read_csv('{W('streets.csv')}', header=true);
CREATE TABLE bst AS SELECT bid, arg_min("name", d) AS street FROM (
  SELECT b.bid, st."name", ST_Distance(st.g, b.c) AS d FROM b JOIN bl USING (bid) JOIN st ON ST_DWithin(st.g, b.c, 0.00027)
  WHERE bl.unit IN ({COT})) GROUP BY bid;
CREATE TABLE bp AS SELECT bid, string_agg(DISTINCT category, '|' ORDER BY category) AS poi
  FROM (SELECT b.bid, p.category FROM b JOIN p ON ST_Intersects(b.g, ST_Buffer(p.g, 0.00004))) GROUP BY bid;
COPY (SELECT b.bid, b.src, b.oid, round(ST_X(b.c), 7) AS lon, round(ST_Y(b.c), 7) AS lat,
        round(b.area, 1) AS area, round(b.perim, 1) AS perim, {', '.join(f'b."{t}"' for t in TAGS)},
        be.eid, bes.estate, bl.unit, bp.poi, bst.street, ST_AsText(ST_ReducePrecision(b.g, 0.0000001)) AS wkt
      FROM b LEFT JOIN be USING (bid) LEFT JOIN bes USING (bid) LEFT JOIN bl USING (bid) LEFT JOIN bp USING (bid) LEFT JOIN bst USING (bid) ORDER BY b.bid)
  TO '{W('buildings-raw.csv')}' (HEADER, DELIMITER ',');
CREATE TABLE cell AS SELECT bid, count(*) OVER (PARTITION BY floor(ST_X(c) * {KX} / 100), floor(ST_Y(c) * 110574.0 / 100)) AS dens FROM b;
COPY (SELECT b.bid, round(ST_X(b.c), 7) AS lon, round(ST_Y(b.c), 7) AS lat, bl.unit, cell.dens
      FROM b LEFT JOIN bl USING (bid) JOIN cell USING (bid) ORDER BY b.bid) TO '{W('buildings-pts.csv')}' (HEADER, DELIMITER ',');
COPY (SELECT eid, kind, areaM2 FROM e ORDER BY eid) TO '{W('enclosure-gates.csv')}' (HEADER, DELIMITER ',');
SELECT count(*) AS footprints, sum(CASE WHEN src='osm' THEN 1 ELSE 0 END) AS osm FROM b;
"""
r = subprocess.run(['duckdb', '-csv'], input=sql, capture_output=True, text=True)
print(r.stdout[-2000:], r.stderr[-3000:])
sys.exit(r.returncode)
