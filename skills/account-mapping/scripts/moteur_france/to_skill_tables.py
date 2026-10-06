"""Convertit la sortie du moteur (out/<groupe>_*.csv) au format du skill account-mapping (6 tables CSV),
pour que scripts/validate_mapping.py et scripts/build_hubspot_import.py marchent tels quels.

Usage : python to_skill_tables.py config/lvmh.json
Écrit out/<groupe>_skill/ : companies, relationships, brands, entities_to_resolve, evidence_sources, coverage.
Aucun nom de personne n'est écrit (licence INPI).
"""
import json, pathlib, sys
from datetime import date
import pandas as pd

cfg = json.load(open(sys.argv[1]))
g = cfg["groupe"].lower()
out = pathlib.Path("out") / f"{g}_skill"
out.mkdir(parents=True, exist_ok=True)
ent = pd.read_csv(f"out/{g}_entites.csv", dtype=str).fillna("")
today = date.today().isoformat()
INPI = "https://data.inpi.fr/entreprises/{}"
ANNUAIRE = "https://annuaire-entreprises.data.gouv.fr/entreprise/{}"


def entity_type(r):
    why = r.raison
    if r.siren == cfg["tete"]:
        return "holding_operating_group"
    if "civile" in why:
        return "sci"
    if "GIE" in why:
        return "shared_service"
    if "Holding" in why:
        return "holding"
    return "operating_company"


companies = pd.DataFrame({
    "company_id": ent.siren, "legal_name": ent.nom, "siren": ent.siren, "siret_hq": ent.siret_siege,
    "hq_address": ent.adresse_siege + " " + ent.commune, "country": "FR", "naf_code": ent.naf,
    "legal_form": ent.forme_juridique, "entity_type": [entity_type(r) for r in ent.itertuples()],
    "operating_status": "active", "targetable": ent.targetable.map({"Oui": "yes", "Non": "no"}),
    "targetable_reason": ent.raison, "domain": "", "domain_scope": "",
    "resolution_status": "resolved", "identity_confidence": "high", "last_verified_at": today,
    "identity_source_url": [ANNUAIRE.format(s) for s in ent.siren],
    "opposition_prospection": ent.opposition_prospection,
    "notes": "Pourquoi dans le groupe : " + ent.pourquoi_dans_le_groupe + " | indices : " + ent.indices,
})

# Une ligne par lien maison mère retenu. A = lu au registre ; B = au moins deux indices ; C = à vérifier.
rel = ent[ent.maison_mere_siren != ""]
relationships = pd.DataFrame({
    "parent_id": rel.maison_mere_siren, "child_id": rel.siren,
    "relationship_type": "control",
    "ownership_pct": "", "control_pct": "",
    "direct_parent_verified": rel.confiance.map({"A": "yes", "B": "no", "C": "no"}),
    "relationship_status": rel.confiance.map({"A": "confirmed", "B": "confirmed", "C": "to_verify"}),
    "valid_from": "", "valid_to": "",
    "confidence": rel.confiance.map({"A": "high", "B": "medium", "C": "low"}),
    "source_url": [INPI.format(s) if c == "A" else ANNUAIRE.format(s) for s, c in zip(rel.siren, rel.confiance)],
    "source_date": today, "notes": rel.type_lien,
})

heads = {}
for r in ent.itertuples():
    if "tête de maison" in r.pourquoi_dans_le_groupe:
        heads[r.nom] = r.siren
brands = pd.DataFrame([{"brand_id": f"B{i + 1}", "brand_name": m, "geography": "FR", "brand_object_type": "brand",
                        "legal_entity_id": next((s for n, s in heads.items() if m.upper().replace("'", " ") in n.upper().replace("'", " ")), ""),
                        "legal_entity_name": "", "domain": "", "mapping_status": "", "source_url": "", "notes": "organigramme public (config)"}
                       for i, m in enumerate(cfg.get("organigramme", []))])
if len(brands):
    brands["mapping_status"] = brands.legal_entity_id.map(lambda x: "mapped" if x else "unresolved")
    brands["legal_entity_name"] = brands.legal_entity_id.map(dict(zip(ent.siren, ent.nom))).fillna("")

queue = []
for f, reason in ((f"out/{g}_participations.csv", "participation sans contrôle (mandat d'administrateur ou de membre seulement)"),
                  (f"out/{g}_etrangeres.csv", "société étrangère avec un SIREN en France")):
    if pathlib.Path(f).exists() and pathlib.Path(f).stat().st_size > 1:
        for r in pd.read_csv(f, dtype=str).fillna("").itertuples():
            queue.append({"candidate_id": r.siren, "entity_name": r.nom, "country": "", "discovery_source": "registre",
                          "official_scope_type": "", "business_segment": "", "control_pct_if_known": "",
                          "resolution_status": "excluded", "next_action": "", "exclusion_reason": reason, "notes": ""})
entities_to_resolve = pd.DataFrame(queue, columns=["candidate_id", "entity_name", "country", "discovery_source", "official_scope_type",
                                                    "business_segment", "control_pct_if_known", "resolution_status", "next_action",
                                                    "exclusion_reason", "notes"])

evidence_sources = pd.DataFrame([
    {"source_id": "S1", "source_name": "Registre national des entreprises (INPI), stock complet", "url": "https://data.inpi.fr", "source_tier": "A", "usage": "mandats entre sociétés, dirigeants", "retrieved_at": today},
    {"source_id": "S2", "source_name": "Base SIRENE (INSEE)", "url": "https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/", "source_tier": "A", "usage": "identité, adresse, effectif", "retrieved_at": today},
    {"source_id": "S3", "source_name": "Organigramme public du groupe (config validée)", "url": "", "source_tier": "B", "usage": "têtes de maison", "retrieved_at": today},
])

n = len(companies)
coverage = pd.DataFrame([{"metric": k, "value": v} for k, v in {
    "root_company_id": cfg["tete"], "mapping_status": "substantially_complete", "recursive_expansion_complete": "yes",
    "companies_resolved": n, "entities_to_resolve_count": len(entities_to_resolve),
    "brands_detected": len(brands), "brands_mapped": int((brands.mapping_status == "mapped").sum()) if len(brands) else 0,
    "direct_parent_verified_pct": round(100 * (rel.confiance == "A").mean(), 1) if len(rel) else 0,
    "source_primary_pct": round(100 * (rel.confiance == "A").mean(), 1) if len(rel) else 0,
    "orphan_count": int((ent.maison_mere_siren == "").sum()) - 1, "targetable_count": int((companies.targetable == "yes").sum()),
}.items()])

for name, df in (("companies", companies), ("relationships", relationships), ("brands", brands),
                 ("entities_to_resolve", entities_to_resolve), ("evidence_sources", evidence_sources), ("coverage", coverage)):
    df.to_csv(out / f"{name}.csv", index=False)
print(f"{out} : {n} sociétés, {len(relationships)} liens, {len(entities_to_resolve)} exclues")
