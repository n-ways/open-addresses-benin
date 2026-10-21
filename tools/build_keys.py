#!/usr/bin/env python3
"""Build model/keys.json for Benin from model/units and model/areas (standard library only).

  python3 tools/build_keys.py

- communes: the 3-letter commune keys (fixed list below; frozen once issued)
- plate names: the short remembered name of every code area (tools/bj_plates.py)
- arrondissements: commune key, number (official ordinal where the name carries
  one, else alphabetical rank after the ordinals, frozen), UTM 31N spot frame
  (origin = SW corner of the outline rounded down to 1 km; 3 or 4 base-20
  characters per axis), and the code areas: the named OSM places inside the
  arrondissement (villages, quartiers...), numbered by alphabetical rank (001...).
  The keys were frozen at first issue; an official list of quartiers (the annex
  of Loi 2013-05) maps onto them through the alias table, never by renumbering.
"""
import csv
import json
import math
import os
import re
import sys
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402

sys.path.insert(0, os.path.join(REPO, 'tools'))
import bj_plates  # noqa: E402

# Commune keys: three letters people can read as the commune's name.
COMMUNES = {
    'Abomey': ('ABO', 'Abomey'), 'Abomey-Calavi': ('CAL', 'Abomey-Calavi'), 'Adja-Ouere': ('ADJ', 'Adja-Ouèrè'),
    'Adjarra': ('ADA', 'Adjarra'), 'Adjohoun': ('ADH', 'Adjohoun'), 'Agbangnizoun': ('AGB', 'Agbangnizoun'),
    'Aguegues': ('AGU', 'Aguégués'), 'Akpo-Misserete': ('AKP', 'Akpro-Missérété'), 'Allada': ('ALL', 'Allada'),
    'Aplahoue': ('APL', 'Aplahoué'), 'Athieme': ('ATH', 'Athiémé'), 'Avrankou': ('AVR', 'Avrankou'),
    'Banikoara': ('BAN', 'Banikoara'), 'Bante': ('BTE', 'Bantè'), 'Bassila': ('BAS', 'Bassila'),
    'Bembereke': ('BEM', 'Bembèrèkè'), 'Bohicon': ('BOH', 'Bohicon'), 'Bonou': ('BON', 'Bonou'), 'Bopa': ('BOP', 'Bopa'),
    'Boukombe': ('BOU', 'Boukoumbé'), 'Come': ('COM', 'Comè'), 'Copargo': ('COP', 'Copargo'), 'Cotonou': ('COT', 'Cotonou'),
    'Cove': ('COV', 'Covè'), 'Dangbo': ('DAN', 'Dangbo'), 'Dassa-Zoume': ('DAS', 'Dassa-Zoumè'),
    'Djakotomey': ('DJA', 'Djakotomey'), 'Djidja': ('DJI', 'Djidja'), 'Djougou': ('DJO', 'Djougou'), 'Dogbo': ('DOG', 'Dogbo'),
    'Glazoue': ('GLA', 'Glazoué'), 'Gogounou': ('GOG', 'Gogounou'), 'Grand-Popo': ('GPO', 'Grand-Popo'),
    'Houeyogbe': ('HOU', 'Houéyogbé'), 'Ifangni': ('IFA', 'Ifangni'), 'Kalale': ('KAL', 'Kalalé'), 'Kandi': ('KAN', 'Kandi'),
    'Karimama': ('KAR', 'Karimama'), 'Kerou': ('KER', 'Kérou'), 'Ketou': ('KET', 'Kétou'), 'Klouekanme': ('KLO', 'Klouékanmè'),
    'Kobli': ('KOB', 'Kobli'), 'Kouande': ('KOU', 'Kouandé'), 'Kpomasse': ('KPO', 'Kpomassè'), 'Lalo': ('LAL', 'Lalo'),
    'Lokossa': ('LOK', 'Lokossa'), 'Malanville': ('MAL', 'Malanville'), 'Materi': ('MAT', 'Matéri'), "N'Dali": ('NDA', "N'Dali"),
    'Natitingou': ('NAT', 'Natitingou'), 'Nikki': ('NIK', 'Nikki'), 'Ouake': ('OUA', 'Ouaké'), 'Ouesse': ('OUE', 'Ouèssè'),
    'Ouidah': ('OUI', 'Ouidah'), 'Ouinhi': ('OUN', 'Ouinhi'), 'Parakou': ('PKO', 'Parakou'), 'Pehunco': ('PEH', 'Péhunco'),
    'Perere': ('PER', 'Pèrèrè'), 'Pobe': ('POB', 'Pobè'), 'Porto-Novo': ('PNO', 'Porto-Novo'), 'Sakete': ('SAK', 'Sakété'),
    'Savalou': ('SVL', 'Savalou'), 'Save': ('SAV', 'Savè'), 'Segbana': ('SEG', 'Ségbana'), 'Seme-Kpodji': ('SEM', 'Sèmè-Podji'),
    'Sinende': ('SIN', 'Sinendé'), 'So-Ava': ('SOA', 'Sô-Ava'), 'Tanguieta': ('TAN', 'Tanguiéta'), 'Tchaourou': ('TCH', 'Tchaourou'),
    'Toffo': ('TOF', 'Toffo'), 'Tori-Bossito': ('TOR', 'Tori-Bossito'), 'Toucountouna': ('TOU', 'Toucountouna'),
    'Toviklin': ('TOV', 'Toviklin'), 'Za-Kpota': ('ZAK', 'Za-Kpota'), 'Zagnanado': ('ZAG', 'Zagnanado'), 'Ze': ('ZEE', 'Zè'),
    'Zogbodomey': ('ZOG', 'Zogbodomey'),
}
PLACE_KINDS = {'village', 'hamlet', 'quarter', 'neighbourhood', 'suburb', 'town', 'city', 'locality'}


def ordinal(name):
    m = re.match(r'^\s*(\d{1,2})\s*(?:er|ère|ème|e|é)\b', name)
    return int(m.group(1)) if m else None


def plain(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).lower()


def main():
    rows = list(csv.DictReader(open(os.path.join(REPO, 'model', 'units', 'arrondissements.csv'), encoding='utf-8')))
    geo = {f['properties']['id']: f for f in json.load(open(os.path.join(REPO, 'model', 'units', 'arrondissements.geojson'),
                                                            encoding='utf-8'))['features']}
    communes = {}
    for r in rows:
        key, name = COMMUNES[r['commune']]
        communes.setdefault(key, {'key': key, 'name': name, 'departement': r['departement'], 'arr': []})['arr'].append(r)
    arrs = []
    for key, c in sorted(communes.items()):
        named = sorted(c['arr'], key=lambda r: (ordinal(r['arrondissement']) is None, ordinal(r['arrondissement']) or 0,
                                               plain(r['arrondissement'])))
        top = max([ordinal(r['arrondissement']) or 0 for r in named] + [0])
        nxt = top + 1
        for r in named:
            o = ordinal(r['arrondissement'])
            if o is None:
                o = nxt
                nxt += 1
            f = geo[r['id']]
            pts = [p for poly in E._rings(f['geometry']) for p in poly[0]]
            us = [E.to_utm(p[1], p[0]) for p in pts]
            e0 = math.floor(min(u[0] for u in us) / 1000) * 1000
            n0 = math.floor(min(u[1] for u in us) / 1000) * 1000
            ex = max(u[0] for u in us) - e0
            ny = max(u[1] for u in us) - n0
            kx = 3 if ex <= 20 ** 3 * E.CELL_M else 4
            ky = 3 if ny <= 20 ** 3 * E.CELL_M else 4
            arrs.append({'id': r['id'], 'commune': key, 'number': o, 'name': r['arrondissement'], 'km2': float(r['km2']),
                         'buildings': int(r['buildings_total']), 'e0': e0, 'n0': n0, 'kx': kx, 'ky': ky, 'digits': 4,
                         'nameRepaired': 'é' in r['arrondissement'] and False, 'places': []})
    # Code areas: the named places inside each arrondissement.
    by_id = {a['id']: a for a in arrs}
    E._keys = {'arrondissements': arrs, '_arr': by_id, '_byCode': {}, '_com': {}}
    for p in csv.DictReader(open(os.path.join(REPO, 'model', 'areas', 'osm-places.csv'), encoding='utf-8')):
        if p['place'] not in PLACE_KINDS:
            continue
        lon, lat = float(p['lon']), float(p['lat'])
        a = E.arrondissement_at(lat, lon)
        if a is None:
            continue
        names = {q['name'] for q in a['places']}
        if p['name'] in names:
            continue
        a['places'].append({'name': p['name'], 'kind': p['place'], 'lon': lon, 'lat': lat})
    for a in arrs:
        a['places'].sort(key=lambda q: plain(q['name']))
        for i, q in enumerate(a['places'], 1):
            q['index'] = i
    # Plate names: at most 12 characters and 2 words, so the code can be said and
    # painted (tools/bj_plates.py). Stored only where they differ from the official
    # name; flagged where the commune may choose another once.
    areas = [{'key': (a['commune'], a['number'], q['index']), 'name': q['name'], 'rec': q}
             for a in arrs for q in a['places']]
    areas += [{'key': (a['commune'], a['number'], 0), 'name': a['name'], 'rec': a} for a in arrs if not a['places']]
    plates = bj_plates.derive_all(areas, {k: c['name'] for k, c in communes.items()})
    for ar in areas:
        r, rec = plates[ar['key']], ar['rec']
        if r['plateName'] != ar['name']:
            rec['plate'] = r['plateName']
        if r['plateRule'] != 'as-is':
            rec['plateRule'] = r['plateRule']
        if r['needsCouncilChoice']:
            rec['needsCouncilChoice'] = True
            rec['plateCandidates'] = r['plateCandidates']
            rec['plateReason'] = r['plateReason']
        if r.get('plateSource'):
            rec['plateSource'] = r['plateSource']
    out = {
        'country': 'BJ', 'version': '1.0', 'built': '2026-10-18',
        'note': ('Code-area keys of Benin, frozen at first issue (20 October 2026). Commune keys are three letters; arrondissement '
                 'numbers are the official ordinal where the name carries one, else the alphabetical rank after the ordinals; '
                 'quartier and village indexes are the alphabetical ranks of the named OpenStreetMap places of each arrondissement. '
                 'name = official name; plate = plate name (the remembered name, at most 12 characters and 2 words) where it '
                 'differs; plateRule, needsCouncilChoice, plateCandidates, plateReason where it was shortened or flagged (an '
                 'arrondissement with no place carries them for its area 000). A flagged area is issued under its provisional '
                 'plate name; the name its commune chooses is added as an alias, and its numbers never change.'),
        'communes': [{k: c[k] for k in ('key', 'name', 'departement')} for _, c in sorted(communes.items())],
        'arrondissements': arrs,
        'sources': {'arrondissements': 'geoBoundaries BEN ADM3 (2021, ODbL; uMap/OpenStreetMap)',
                    'communes': 'OCHA COD-AB Benin admin2 (CC BY-IGO)', 'places': 'OpenStreetMap (ODbL), 2026-10-17 extract'},
    }
    json.dump(out, open(os.path.join(REPO, 'model', 'keys.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(len(out['communes']), 'communes,', len(arrs), 'arrondissements,', sum(len(a['places']) for a in arrs), 'places;',
          'frames 6/7/8 chars:', sum(1 for a in arrs if a['kx'] + a['ky'] == 6), sum(1 for a in arrs if a['kx'] + a['ky'] == 7),
          sum(1 for a in arrs if a['kx'] + a['ky'] == 8))
    dup = {}
    for a in arrs:
        dup.setdefault((a['commune'], a['number']), []).append(a['name'])
    bad = {k: v for k, v in dup.items() if len(v) > 1}
    if bad:
        print('duplicate numbers:', bad)


if __name__ == '__main__':
    main()
