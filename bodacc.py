"""Recherche dans les annonces du BODACC les sociétés où une société donnée est nommée dirigeante.

Le BODACC est la seule source publique gratuite qui permet de chercher dans ce sens
("où X est-elle présidente, gérante, administratrice ?"). Les résultats servent à découvrir
des candidates ; le lien est ensuite vérifié sur la fiche RNE de la candidate.
"""
import hashlib, json, pathlib, re, time, urllib.parse, requests

BASE = "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales"
CACHE = pathlib.Path(__file__).parent / "data" / "bodacc"
CACHE.mkdir(parents=True, exist_ok=True)

# Rôles qui ne disent rien du contrôle : on ne les lit jamais comme un lien de groupe.
EXCLUDED = re.compile(r"commissaire|liquidat|administrateur judiciaire|administrateur provisoire|mandataire|repr[ée]sentant fiscal|contr[ôo]leur|comptable|avocat|expert", re.I)
ROLES = [("president", re.compile(r"pr[ée]sident", re.I)), ("gerant", re.compile(r"g[ée]rant", re.I)),
         ("associe", re.compile(r"associ[ée]", re.I)), ("administrateur", re.compile(r"administrat", re.I)),
         ("membre", re.compile(r"membre", re.I))]


def _export(where):
    key = hashlib.sha1(where.encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text())
    url = f"{BASE}/exports/json?where={urllib.parse.quote(where)}&select=registre,commercant,dateparution,familleavis,listepersonnes"
    for attempt in range(5):
        try:
            r = requests.get(url, timeout=300)
            if r.status_code == 200:
                f.write_text(r.text)
                return r.json()
        except requests.exceptions.RequestException:
            pass
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"BODACC indisponible : {where}")


def _sirens(rec):
    out = set()
    for x in rec.get("registre") or []:
        s = re.sub(r"\D", "", x)
        if len(s) == 9:
            out.add(s)
    return out


LEGAL_FORMS = {"SA", "SAS", "SASU", "SARL", "SNC", "SE", "SCA", "SCS", "EURL", "GIE", "SC"}


def officer_of(name, own_siren=None, longer_name=None):
    """Annonces où la société `name` apparaît dans le bloc "administration" d'une autre société.

    Le nom doit être écrit en majuscules (le BODACC écrit ainsi les sociétés, les prénoms sont en
    minuscules : "DUPONT Celine" ne doit pas matcher la société CELINE). `longer_name(name, mot)`
    dit si "name mot" est le début d'un autre nom de société (MOET HENNESSY INVESTISSEMENTS).
    Renvoie {siren_cible: {"role", "date", "partant", "texte"}} avec la dernière annonce connue.
    """
    name = name.strip().upper()
    if len(name) < 4:
        return {}
    pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])")
    found = {}
    for rec in _export(f'listepersonnes like "%{name}%"'):
        try:
            lp = json.loads(rec.get("listepersonnes") or "{}").get("personne") or {}
        except json.JSONDecodeError:
            continue
        for pers in (lp if isinstance(lp, list) else [lp]):
            admin = (pers.get("administration") or "")
            for seg in admin.split(";"):
                m = pattern.search(seg)
                if not m:
                    continue
                # "NOM Prénom" (nom de famille puis prénom) est une personne, pas la société homonyme.
                if re.match(r"\s*,?\s*[A-ZÉÈ][a-zéèêëàâîïôöûüç]+", seg[m.end():]):
                    continue
                nxt = re.match(r"\s*([A-Z][A-Z0-9'&-]+)\b", seg[m.end():])
                if nxt and nxt.group(1) not in LEGAL_FORMS and longer_name and longer_name(name, nxt.group(1)):
                    continue
                # Le rôle est celui écrit juste avant le nom, dans la même phrase.
                head = re.split(r"[.]\s", seg[:m.start()])[-1]
                if EXCLUDED.search(head.split(":")[-2] if head.count(":") >= 2 else head):
                    continue
                hits = [(mm.start(), r) for r, rx in ROLES for mm in rx.finditer(head)]
                role = max(hits)[1] if hits else "autre"
                for s in _sirens(rec) - {own_siren}:
                    prev = found.get(s)
                    if prev is None or rec["dateparution"] >= prev["date"]:
                        found[s] = {"role": role, "date": rec["dateparution"], "partant": "partant" in seg.lower(),
                                    "texte": seg.strip()[:200]}
    return found
