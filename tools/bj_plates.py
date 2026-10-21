#!/usr/bin/env python3
"""Plate names for Benin: the short remembered name of every code area.

The name part of a remembered code is at most 12 characters and at most 2
words ("Soukoumpérou · 10 01", never "Camp Peulh Soukoumpérou · 10 01"): it is
said on the phone and painted on a gate. The rule itself is
engine/reference/plate_names.py; this file is Benin's configuration:

  lang          'fr' (French generic words; the names themselves are Fon, Gun,
                Yoruba/Nago, Bariba, Fulfulde, Dendi...)
  DIGITS_OK     True: Benin names carry ordinals ('Ganvié 1', 'Agué 2') and the
                written form keeps them apart from the number with '·'
  GENERIC_EXTRA French words of Benin place labels that are never the
                remembered part
  WEAK_EXTRA    words that are a real part of a name but never a plate name on
                their own: Peulh, Gah, Gouré, Gnel (Fulani camps and hamlets),
                Bariba, Gando, Kparou, Camp, Centre, Gare, Plage...
  fold          none: a doubled word is the name itself ("Wari Wari", "Kiti
                Kiti"), not a second spelling, so it is never removed
  KNOWN         documented short forms, each with a source (none yet)
  LINKING       + 'es' (Arabic article); BINDING + Aladji, Orou, Bio, Sabi (the
                first part of a person's name is never left alone or cut off)
  avoid         the 12 department names, the 77 commune seats (which include the 12 department
                capitals), the short forms people use for some of them, and the
                big towns of the neighbouring countries; the area's own commune is removed

  python3 tools/bj_plates.py [N]     print N random results (default 60)
"""
import collections
import os
import re
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import bj_engine as E  # noqa: E402
import plate_names as P  # noqa: E402

LANG = 'fr'
# DIGITS_OK and the linking word 'es' are set by the engine itself (bj_engine).
P.BINDING |= {'aladji', 'alhadji', 'elhadj', 'el-hadj', 'orou', 'bio', 'sabi'}  # "Aladji Djiman", "Orou Boba": a person's name is never cut

GENERIC_EXTRA = ['site des logements sociaux', 'logements sociaux', 'village peulh de']
# Weak words are real parts of names but never a plate name alone; one that
# follows the name is a qualifier, which only the commune may drop.
# Peulh, Bariba, Gando, Dendi, Haoussa name the people of a settlement ("Nanankpo
# Bariba" and "Nanankpo Peulh" are two places): never dropped without the commune.
WEAK_EXTRA = {'peulh', 'peuhl', 'peul', 'bariba', 'gando', 'dendi', 'haoussa', 'gah', 'camp', 'arrondissement',
              'arrondisement', 'site', 'ferme', 'poste', 'forestier', 'centre', 'carrefour', 'marché', 'gare', 'plage',
              'barrage', 'ecole', 'école', 'mission', 'jardin', 'ouvrière', 'ouvrier', 'latin', 'industrielle', 'résidentielle',
              'administrative', 'commerciale', 'aéroport', 'place', 'publique', 'public', 'logements', 'logement',
              'sociaux', 'social', 'forêt', 'foret', 'sacrée', 'sacree',
              # settlement words of the north (Fulani hamlets, Bariba quarters) that head or end
              # many names: "Gouré Aladji Djiman", "Gnel Tchankolidjèl", "El Hadj Halidou Kparou"
              'gouré', 'gourè', 'goure', 'gnel', 'kparou', "n'kparou"}
# Labels in the map that are not place names.
NOT_NAMES = {'vous etes ici', 'ici', 'nom_loc'}
KNOWN = {}

# Short forms in everyday use for communes with a compound name.
COMMUNE_SHORT = {'Abomey-Calavi': ['Calavi'], 'Dassa-Zoumè': ['Dassa'], 'Akpro-Missérété': ['Missérété'],
                 'Sèmè-Podji': ['Sèmè'], 'Grand-Popo': [], 'Porto-Novo': [], 'Tori-Bossito': ['Bossito'],
                 'Adja-Ouèrè': [], 'Za-Kpota': [], 'Sô-Ava': []}
# Towns a plate name must not equal: the big towns of the four neighbouring
# countries (a parcel for "Kara · 12 03" should not look bound for Kara), the
# neighbours' names, and the 12 departments.
REGION = ['Lagos', 'Abuja', 'Ibadan', 'Kano', 'Lomé', 'Kara', 'Sokodé', 'Atakpamé', 'Aného', 'Kpalimé',
          'Dapaong', 'Niamey', 'Ouagadougou',
          'Bénin', 'Nigeria', 'Niger', 'Togo', 'Burkina',
          # the 12 departments
          'Alibori', 'Atacora', 'Atlantique', 'Borgou', 'Collines', 'Couffo', 'Donga', 'Littoral', 'Mono', 'Ouémé',
          'Plateau', 'Zou']
CAMP = re.compile(r'^(?:camp|campement)\s+(?=peu)', re.I)   # "Camp Peulh Tovari" -> "Peulh Tovari"


def _pre(official):
    """Benin pre-cleaning: "Camp Peulh X" is said "Peulh X" (the Fulani camp of X);
    a name written in capitals gets ordinary capitals on the plate."""
    s = CAMP.sub('', official.strip())
    s = re.sub(r'\s*\bnom_loc\b', '', s).strip()   # a mapping placeholder, not part of the name
    if s.upper() == s and any(c.isalpha() for c in s):
        s = ' '.join('-'.join(w[:1] + w[1:].lower() if len(w) >= 4 else w for w in u.split('-')) for u in s.split())
    return s


def commune_names():
    return {c['key']: c['name'] for c in E.keys()['communes']}


def town_forms(commune_name):
    return [commune_name] + COMMUNE_SHORT.get(commune_name, [])


def derive_all(areas, communes=None):
    """areas: [{'key': (commune, arr, quartier), 'name': official}] ->
    {key: {'plateName', 'officialName', 'plateRule', 'needsCouncilChoice', 'plateCandidates', 'plateReason'}}"""
    cn = communes or commune_names()
    freq = P.word_freq([a['name'] for a in areas], LANG)
    all_towns = {E.norm_name(t) for c in cn.values() for t in town_forms(c)} | {E.norm_name(t) for t in REGION}
    out = {}
    for a in areas:
        own = {E.norm_name(t) for t in town_forms(cn[a['key'][0]])}
        avoid = all_towns - own
        pre = _pre(a['name'])
        if P.plain(a['name']).strip() in NOT_NAMES:
            out[a['key']] = {'plateName': pre, 'officialName': a['name'], 'plateRule': 'council',
                             'needsCouncilChoice': True, 'plateCandidates': [],
                             'plateReason': 'not a place name (a mapping error): the commune names the area'}
            continue
        r = P.derive(pre, LANG, freq, known=KNOWN, avoid=avoid, generic_extra=GENERIC_EXTRA,
                     weak_extra=WEAK_EXTRA, fold=None, avoid_key=E.norm_name)
        if pre != a['name'] and r['rule'] == 'as-is':
            r['rule'] = 'cleaned'
        if r['needsCouncilChoice'] and not r['candidates'] and '-' in r['plate']:
            # A hyphenated name joins two names ("Hounsa-Assiogbossa"): its parts are
            # candidates, never an automatic choice.
            whole = r['plate']
            cs = []
            for c in P.candidates(whole.replace('-', ' '), LANG, freq, WEAK_EXTRA):
                h = c[0].replace(' ', '-')
                c = h if h.lower() in whole.lower() else c[0]
                c = c[:1].upper() + c[1:]
                if E.norm_name(c) not in avoid and sum(ch.isalpha() for ch in c) >= P.MIN_LETTERS \
                        and not re.search(r'\d', c.split()[0]):
                    cs.append(c)
            if cs:
                r.update(plate=cs[0], candidates=cs[:3],
                         reason='hyphenated name: the commune chooses the part people say')
        if r['needsCouncilChoice'] and r['rule'] == 'council':
            # a candidate is a name: 4 letters or more, not a number or a generic word alone
            gen = {P.plain(g) for g in P.GENERIC[LANG]} | {P.plain(g) for g in GENERIC_EXTRA}
            ok = [c for c in r['candidates'] if sum(ch.isalpha() for ch in c) >= P.MIN_LETTERS
                  and not re.match(r'\d', c) and P.plain(c) not in gen]
            if ok != r['candidates']:
                r['candidates'] = ok
                if not ok:
                    r['plate'] = P.clean(pre, LANG, GENERIC_EXTRA, WEAK_EXTRA)[0]
                    r['reason'] = 'no run of whole words fits %d characters and %d words' % (P.MAX_CHARS, P.MAX_WORDS)
                elif r['plate'] not in ok:
                    r['plate'] = ok[0]
        rec = {'plateName': r['plate'], 'officialName': a['name'], 'plateRule': r['rule'],
               'needsCouncilChoice': r['needsCouncilChoice']}
        if r.get('source'):
            rec['plateSource'] = r['source']
        if r['needsCouncilChoice']:
            rec['plateCandidates'] = r['candidates'][:3]
            rec['plateReason'] = r.get('reason', '')
        out[a['key']] = rec
    return out


def all_areas():
    out = []
    for a in E.keys()['arrondissements']:
        for p in a['places'] or [{'index': 0, 'name': a['name']}]:
            out.append({'key': (a['commune'], a['number'], p['index']), 'name': p['name']})
    return out


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    res = derive_all(all_areas())
    rules = collections.Counter(r['plateRule'] for r in res.values())
    print(rules, 'flagged', sum(r['needsCouncilChoice'] for r in res.values()),
          'over', sum(not P.fits(r['plateName'], LANG) for r in res.values()))
    changed = [r for r in res.values() if r['plateRule'] != 'as-is']
    random.seed(int(os.environ.get('SEED', '3')))
    for r in random.sample(changed, min(n, len(changed))):
        print(f"{r['plateRule']:11} {r['officialName']!r:45} -> {r['plateName']!r:20} {r.get('plateCandidates', '')} {r.get('plateReason', '')}")
