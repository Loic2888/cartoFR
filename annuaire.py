"""Recherche dans l'API Recherche d'entreprises (annuaire-entreprises.data.gouv.fr) les sociétés
dont une société donnée est dirigeante.

La recherche plein texte de l'API couvre aussi les noms des dirigeants personnes morales, et chaque
résultat donne le SIREN de ces dirigeants : on ne garde que les résultats où ce SIREN est exactement
celui de la société du groupe, ce qui écarte les homonymes. Gratuit, sans compte, 7 requêtes/seconde.
"""
import hashlib, json, pathlib, re, time, requests

BASE = "https://recherche-entreprises.api.gouv.fr/search"
CACHE = pathlib.Path(__file__).parent / "data" / "annuaire"
CACHE.mkdir(parents=True, exist_ok=True)
EXCLUDED = re.compile(r"commissaire|liquidat|judiciaire|provisoire|mandataire|fiscal|contr[ôo]leur|comptable|avocat|expert", re.I)
MAX_PAGES = 40  # 1 000 résultats ; au-delà le nom est trop courant pour que la recherche serve
_last = 0.0


def _get(params):
    global _last
    for attempt in range(6):
        time.sleep(max(0, _last + 0.2 - time.time()))
        _last = time.time()
        try:
            r = requests.get(BASE, params=params, timeout=30)
        except requests.exceptions.RequestException:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    return None


def officer_of(name, siren):
    """{siren_cible: qualité} pour les sociétés actives où `siren` (nommée `name`) est dirigeante."""
    key = hashlib.sha1(f"{name}|{siren}".encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text())
    found = {}
    page, pages = 1, 1
    while page <= min(pages, MAX_PAGES):
        d = _get({"q": name, "per_page": 25, "page": page, "etat_administratif": "A"})
        if d is None:
            break
        pages = d.get("total_pages", 1)
        for r in d.get("results", []):
            for x in r.get("dirigeants", []):
                if x.get("type_dirigeant") == "personne morale" and x.get("siren") == siren and r["siren"] != siren:
                    q = x.get("qualite") or ""
                    if not EXCLUDED.search(q):
                        found[r["siren"]] = q
        page += 1
    f.write_text(json.dumps(found))
    return found
