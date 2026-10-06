#!/usr/bin/env python3
"""Contrôle une cartographie de compte avant livraison.

Entrée, au choix :
- un dossier de CSV, un fichier par table (companies.csv, relationships.csv, ...) : format par défaut ;
- un classeur XLSX, un onglet par table (demande openpyxl).

Usage : validate_mapping.py <dossier_csv | fichier.xlsx>
Code de sortie : 0 si aucune erreur bloquante, 1 sinon, 2 si l'entrée est illisible.
"""
import csv
import io
import sys
from pathlib import Path

REQUIRED_TABLES = {
    "companies",
    "relationships",
    "brands",
    "entities_to_resolve",
    "coverage",
}
# La table des sources s'appelle `evidence_sources` dans references/data-model.md et dans SKILL.md.
# L'ancien nom `sources` reste accepté pour les fichiers déjà produits.
SOURCE_TABLE_NAMES = ("evidence_sources", "sources")

REQUIRED_COMPANY_COLUMNS = {
    "company_id", "legal_name", "targetable", "targetable_reason",
    "entity_type", "resolution_status"
}
REQUIRED_REL_COLUMNS = {
    "parent_id", "child_id", "relationship_type", "relationship_status",
    "confidence", "source_url"
}


def clean(value):
    # Une cellule vide vaut None, qu'elle vienne d'un CSV ("") ou d'Excel (None). Les espaces autour sont retirés.
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def read_csv(path):
    # utf-8-sig retire le BOM qu'Excel ajoute en tête de fichier
    raw = path.read_text(encoding="utf-8-sig")
    header_line = raw.split("\n", 1)[0]
    # Excel en français exporte avec « ; » : on prend le séparateur le plus présent sur la ligne d'en-tête
    delimiter = ";" if header_line.count(";") > header_line.count(",") else ","
    rows = list(csv.reader(io.StringIO(raw), delimiter=delimiter))
    if not rows:
        return [], []
    return [clean(h) for h in rows[0]], rows[1:]


def load_tables(path):
    """Lit un dossier de CSV ou un classeur XLSX. Renvoie ({table: [lignes en dict]}, {table: [en-têtes]}, format)."""
    p = Path(path)
    raw_tables = {}
    if p.is_dir():
        fmt = "csv"
        for f in sorted(p.glob("*.csv")):
            raw_tables[f.stem] = read_csv(f)
    elif p.suffix.lower() in {".xlsx", ".xlsm"}:
        fmt = "xlsx"
        from openpyxl import load_workbook  # importé ici : inutile pour un dossier CSV
        wb = load_workbook(p, data_only=False, read_only=True)
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            header_row = next(it, None) or ()
            raw_tables[ws.title] = ([clean(h) for h in header_row], list(it))
    else:
        raise ValueError(f"entrée non reconnue : {p} (attendu : un dossier de CSV ou un fichier .xlsx)")

    tables, headers = {}, {}
    for name, (hs, rows) in raw_tables.items():
        headers[name] = [h for h in hs if h is not None]
        out = []
        for values in rows:
            values = [clean(v) for v in values]
            if not any(v is not None for v in values):
                continue  # ligne vide
            out.append({h: v for h, v in zip(hs, values) if h is not None})
        tables[name] = out
    return tables, headers, fmt


def missing_label(fmt, names):
    if fmt == "csv":
        return f"Fichiers manquants dans le dossier: {sorted(n + '.csv' for n in names)}"
    return f"Onglets manquants: {sorted(names)}"


def check(tables, headers, fmt):
    """Renvoie (erreurs, avertissements)."""
    errors, warnings = [], []

    missing = REQUIRED_TABLES - set(tables)
    if not any(n in tables for n in SOURCE_TABLE_NAMES):
        missing.add("evidence_sources")
    if missing:
        errors.append(missing_label(fmt, missing))
        return errors, warnings

    ch = set(headers["companies"])
    rh = set(headers["relationships"])
    if REQUIRED_COMPANY_COLUMNS - ch:
        errors.append(f"Colonnes companies manquantes: {sorted(REQUIRED_COMPANY_COLUMNS - ch)}")
    if REQUIRED_REL_COLUMNS - rh:
        errors.append(f"Colonnes relationships manquantes: {sorted(REQUIRED_REL_COLUMNS - rh)}")

    companies = tables["companies"]
    relationships = tables["relationships"]
    brands = tables["brands"]
    queue = tables["entities_to_resolve"]

    ids = [r.get("company_id") for r in companies if r.get("company_id")]
    duplicate_ids = sorted({x for x in ids if ids.count(x) > 1})
    if duplicate_ids:
        errors.append(f"company_id dupliqués: {duplicate_ids}")
    id_set = set(ids)

    for r in companies:
        t = r.get("targetable")
        if t not in {"yes", "no"}:
            errors.append(f"targetable invalide pour {r.get('company_id')}: {t!r}")
        if not r.get("targetable_reason"):
            warnings.append(f"targetable_reason vide pour {r.get('company_id')}")

    for r in relationships:
        parent = r.get("parent_id")
        child = r.get("child_id")
        if parent and parent not in id_set:
            errors.append(f"parent_id absent de companies: {parent}")
        if child and child not in id_set:
            errors.append(f"child_id absent de companies: {child}")
        if r.get("relationship_status") == "confirmed" and not r.get("source_url"):
            errors.append(f"relation confirmed sans source: {parent} -> {child}")

    unresolved_brands = sum(1 for r in brands if str(r.get("mapping_status") or "").lower() not in {"mapped", "resolved", "not_a_legal_entity"})
    open_queue = sum(1 for r in queue if str(r.get("resolution_status") or "").lower() not in {"resolved", "excluded", "not_a_legal_entity", "duplicate", "unresolvable"})
    if unresolved_brands:
        warnings.append(f"{unresolved_brands} marques/objets restent non résolus")
    if open_queue:
        warnings.append(f"{open_queue} entités restent ouvertes dans entities_to_resolve")

    return errors, warnings


def print_report(errors, warnings):
    print(f"Errors: {len(errors)}")
    for e in errors:
        print(f"  - {e}")
    print(f"Warnings: {len(warnings)}")
    for w in warnings[:100]:
        print(f"  - {w}")


def main(path):
    p = Path(path)
    if not p.exists():
        print(f"ERROR: fichier ou dossier introuvable: {p}")
        return 2
    try:
        tables, headers, fmt = load_tables(p)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 2
    errors, warnings = check(tables, headers, fmt)
    print_report(errors, warnings)
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: validate_mapping.py <dossier_csv | fichier.xlsx>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
