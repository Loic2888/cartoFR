"""Étape 4 : chercher dans toute la base SIRENE les sociétés actives dont le nom commence par une marque du groupe.

Usage : python brand_scan.py config/lvmh.json
Écrit out/<groupe>_candidates.csv.
"""
import json, re, sys, unicodedata, duckdb

# Formes juridiques qu'on accepte devant la marque : « STE CIVILE CHATEAU YQUEM » est candidate.
PREFIXES = ["SOCIETE CIVILE IMMOBILIERE", "SOCIETE CIVILE", "STE CIVILE", "SOCIETE", "STE", "SCI", "SCEA", "SCE", "GFA", "GFV", "GAEC", "EARL",
            "SA", "SAS", "SASU", "SARL", "EURL", "SNC", "SC", "GIE", "SE", "SCA", "SOC", "CIE", "COMPAGNIE", "ETS", "ETABLISSEMENTS", "LES", "LE", "LA", "L", "DES", "DU", "DE", "D"]


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    s = s.replace("&", " ET ")
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def main(cfg_path):
    cfg = json.load(open(cfg_path))
    brands = [(norm(b), "sure") for b in cfg["marques_sures"]] + [(norm(b), "ambigue") for b in cfg["marques_ambigues"]]
    c = duckdb.connect()
    c.create_function("norm", norm, ["VARCHAR"], "VARCHAR")
    # Personnes morales actives seulement : les entrepreneurs individuels (catégorie 1000) sont écartés d'office.
    c.sql("""
        create table ul as
        select siren, categorieJuridiqueUniteLegale cj, activitePrincipaleUniteLegale naf, trancheEffectifsUniteLegale tranche,
               nicSiegeUniteLegale nic, dateCreationUniteLegale creation,
               norm(coalesce(denominationUniteLegale, '')) n0, norm(coalesce(sigleUniteLegale, '')) n1,
               norm(coalesce(denominationUsuelle1UniteLegale, '')) n2, denominationUniteLegale nom
        from 'data/unite_legale.parquet'
        where etatAdministratifUniteLegale = 'A' and categorieJuridiqueUniteLegale <> 1000 and denominationUniteLegale is not null
    """)
    prefix_re = "(?:(?:" + "|".join(PREFIXES) + ") )*"
    rows = []
    for b, kind in brands:
        pat = "^" + prefix_re + re.escape(b) + "( |$)"
        for r in c.execute(f"select siren, nom, cj, naf, tranche, nic, creation from ul where regexp_matches(n0, ?) or regexp_matches(n1, ?) or regexp_matches(n2, ?)", [pat, pat, pat]).fetchall():
            rows.append((*r, b, kind))
    import pandas as pd
    df = pd.DataFrame(rows, columns=["siren", "nom", "categorie_juridique", "naf", "tranche_effectif", "nic_siege", "creation", "marque", "type_marque"])
    # Une société peut matcher plusieurs marques : on garde la plus longue (la plus précise).
    df["len"] = df.marque.str.len()
    df = df.sort_values("len", ascending=False).drop_duplicates("siren").drop(columns="len")
    out = f"out/{cfg['groupe'].lower()}_candidates.csv"
    df.to_csv(out, index=False)
    print(out, len(df), "candidates", df.type_marque.value_counts().to_dict())


if __name__ == "__main__":
    main(sys.argv[1])
