"""Petit client pour l'API RNE de l'INPI. Lit les identifiants dans zyzx/.env, ne les affiche jamais."""
import json, os, pathlib, time, requests

BASE = "https://registre-national-entreprises.inpi.fr/api"
HERE = pathlib.Path(__file__).parent
CACHE = HERE / "data" / "rne"
CACHE.mkdir(parents=True, exist_ok=True)
_token = None
_last = 0.0
DELAY = 1.0


def _env():
    vals = {}
    for line in (HERE / ".env").read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def token():
    global _token
    if _token is None:
        e = _env()
        r = requests.post(f"{BASE}/sso/login", json={"username": e["INPI_USERNAME"], "password": e["INPI_PASSWORD"]}, timeout=30)
        r.raise_for_status()
        _token = r.json()["token"]
    return _token


def company(siren, refresh=False):
    """Fiche RNE complète d'une société, mise en cache sur disque."""
    f = CACHE / f"{siren}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text())
    global _last, _token
    for attempt in range(8):
        # Une requête par seconde au plus : au-delà, l'INPI coupe la connexion.
        time.sleep(max(0, _last + DELAY - time.time()))
        _last = time.time()
        try:
            r = requests.get(f"{BASE}/companies/{siren}", headers={"Authorization": f"Bearer {token()}"}, timeout=60)
        except requests.exceptions.RequestException:
            time.sleep(60 * (attempt + 1))
            continue
        if r.status_code == 429:
            time.sleep(60 * (attempt + 1))
            continue
        if r.status_code == 401:
            # La clé de connexion INPI a expiré : on se reconnecte et on recommence.
            _token = None
            continue
        if r.status_code == 404:
            f.write_text("null")
            return None
        if r.status_code >= 500:
            # Erreur côté INPI sur une fiche : on réessaie un peu, puis on la saute sans bloquer le reste.
            if attempt >= 2:
                return None
            time.sleep(10)
            continue
        r.raise_for_status()
        f.write_text(r.text)
        return r.json()
    raise RuntimeError(f"quota INPI : {siren}")
