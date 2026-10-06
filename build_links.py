"""Construit, depuis le stock RNE complet de l'INPI, les tables locales qui remplacent les appels d'API.

Usage : python build_links.py data/rne_stock/stock_RNE_formalites_NIVEAU1_20260304_1400.zip
Écrit dans data/rne_links/ :
- liens.parquet : une ligne par lien "société parent dirige société enfant" (rôle RNE, actif ou non) ;
- personnes.parquet : dirigeants personnes physiques par société, sous forme de clé (nom|prénom|naissance).
  Usage interne seulement, comme preuve : jamais affiché ni exporté (licence INPI) ;
- societes.parquet : opposition à la prospection et effectif déclaré, par société.
Le zip est lu morceau par morceau, sur plusieurs cœurs, sans rien décompresser sur le disque.
"""
import multiprocessing as mp, os, pathlib, sys, zipfile
import ijson, pyarrow as pa, pyarrow.parquet as pq

OUT = pathlib.Path(__file__).parent / "data" / "rne_links"
PARTS = OUT / "parts"


def parse(args):
    zpath, name = args
    done = PARTS / f"{name}.done"
    if done.exists():
        return name
    liens, pers, socs = [], [], []
    with zipfile.ZipFile(zpath) as z, z.open(name) as f:
        for c in ijson.items(f, "item", use_float=True):
            fo = c.get("formality") or {}
            siren = fo.get("siren") or c.get("siren")
            pm = (fo.get("content") or {}).get("personneMorale")
            if not siren or not pm:
                continue
            ent = ((pm.get("identite") or {}).get("entreprise") or {})
            socs.append((siren, ent.get("denomination"), fo.get("diffusionCommerciale"), fo.get("diffusionINSEE"),
                         ent.get("nombreSalarie"), c.get("updatedAt")))
            for p in (pm.get("composition") or {}).get("pouvoirs") or []:
                code, actif = p.get("roleEntreprise"), p.get("actif")
                if p.get("typeDePersonne") == "ENTREPRISE":
                    e = p.get("entreprise") or {}
                    if e.get("siren"):
                        liens.append((e["siren"], siren, code, actif, e.get("denomination")))
                elif p.get("typeDePersonne") == "INDIVIDU":
                    dp = (p.get("individu") or {}).get("descriptionPersonne") or {}
                    nom = (dp.get("nom") or "").upper()
                    if nom:
                        key = f"{nom}|{((dp.get('prenoms') or [''])[0] or '').upper()}|{dp.get('dateDeNaissance', '')}"
                        pers.append((siren, key, code, actif))
    stem = name.replace(".json", "")
    pq.write_table(pa.table(list(zip(*liens)) or [[]] * 5, names=["parent", "enfant", "role", "actif", "parent_nom"]) if liens else
                   pa.table({"parent": [], "enfant": [], "role": [], "actif": [], "parent_nom": []}), PARTS / f"{stem}_liens.parquet")
    pq.write_table(pa.table(list(zip(*pers)), names=["siren", "personne", "role", "actif"]) if pers else
                   pa.table({"siren": [], "personne": [], "role": [], "actif": []}), PARTS / f"{stem}_personnes.parquet")
    pq.write_table(pa.table(list(zip(*socs)), names=["siren", "denomination", "diffusion_commerciale", "diffusion_insee", "salaries", "maj"]) if socs else
                   pa.table({"siren": [], "denomination": [], "diffusion_commerciale": [], "diffusion_insee": [], "salaries": [], "maj": []}),
                   PARTS / f"{stem}_societes.parquet")
    done.write_text("ok")
    return name


if __name__ == "__main__":
    zpath = sys.argv[1]
    PARTS.mkdir(parents=True, exist_ok=True)
    names = [i.filename for i in zipfile.ZipFile(zpath).infolist() if i.filename.endswith(".json")]
    workers = max(1, (os.cpu_count() or 2) - 2)
    print(f"{len(names)} fichiers, {workers} cœurs", flush=True)
    with mp.Pool(workers) as pool:
        for i, _ in enumerate(pool.imap_unordered(parse, [(zpath, n) for n in names]), 1):
            if i % 250 == 0 or i == len(names):
                print(f"{i}/{len(names)} fichiers lus", flush=True)
    import duckdb
    db = duckdb.connect()
    for t in ("liens", "personnes", "societes"):
        db.sql(f"copy (select * from '{PARTS}/*_{t}.parquet') to '{OUT}/{t}.parquet' (format parquet)")
        print(t, db.sql(f"select count(*) from '{OUT}/{t}.parquet'").fetchone()[0], "lignes", flush=True)
    print("FIN", flush=True)
