#!/usr/bin/env python3
"""Prépare l'import HubSpot d'une cartographie de compte.

Produit deux fichiers à côté de l'entrée :
- `hubspot_import.csv` : une ligne par société à créer dans HubSpot, avec son niveau ;
- `hubspot_associations.csv` : une ligne par lien société -> parent, une société pouvant avoir plusieurs parents.

Usage : build_hubspot_import.py <dossier_csv | fichier.xlsx> [--root <company_id>] [--out-dir <dossier>]

Règles (détail dans SKILL.md, section « Import HubSpot ») :
1. Sont importées les sociétés `targetable = yes`, plus la racine du groupe même si elle ne l'est pas,
   pour que toutes les filiales se rattachent au même groupe. La racine se lit dans `coverage`
   (`root_company_id`) ou se passe avec --root.
2. Une société non importée (holding, SCI, SPV...) n'est jamais dans HubSpot : on la saute et la filiale
   se rattache à la société importée située au-dessus.
3. Seuls les liens `confirmed` où une société détient ou contrôle l'autre font un parent : ownership,
   control, joint_venture, associate, branch_of. Consolidation, marque, service partagé, lien
   institutionnel n'en font pas.
4. Une société détenue par plusieurs sociétés importées a plusieurs parents. Le parent principal
   (`primary_parent = yes`) est celui qui a le plus fort `control_pct`, puis le plus fort `ownership_pct` :
   c'est lui qui prend le lien natif « Parent company » de HubSpot, limité à un seul. Sans gagnant net
   (joint venture 50/50, pourcentages manquants), il n'y a pas de parent principal.
5. `hubspot_level` vaut 0 sans parent, sinon 1 + le plus haut niveau de ses parents : en important
   niveau par niveau, tous les parents d'une société existent avant elle.
"""
import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

from validate_mapping import check, load_tables, print_report

PARENT_TYPES = {"ownership", "control", "joint_venture", "associate", "branch_of"}
ASSOCIATION_COLUMNS = [
    "child_level",
    "child_company_id",
    "child_legal_name",
    "child_siren",
    "parent_company_id",
    "parent_legal_name",
    "parent_siren",
    "ownership_pct",
    "control_pct",
    "primary_parent",
    "via",
]


def pct(value):
    # Accepte 51, "51", "51%", "51,5 %" ; renvoie None si vide ou illisible
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None


def fmt_pct(value):
    if value is None:
        return None
    return int(value) if float(value).is_integer() else value


def keep_max(a, b):
    values = [v for v in (a, b) if v is not None]
    return max(values) if values else None


def read_root(coverage):
    # coverage peut être « large » (une colonne root_company_id) ou « long » (lignes métrique / valeur)
    for row in coverage:
        if row.get("root_company_id"):
            return row["root_company_id"]
        values = list(row.values())
        if len(values) >= 2 and values[0] == "root_company_id":
            return values[1]
    return None


def build(tables, headers, root_id):
    companies = tables["companies"]
    by_id = {c["company_id"]: c for c in companies if c.get("company_id")}

    # Parents directs de chaque société. Deux lignes pour le même couple (ex. ownership + control)
    # sont fusionnées en gardant les plus forts pourcentages.
    direct = defaultdict(dict)
    other_links = defaultdict(set)  # liens qui ne font pas un parent (consolidation...), cités dans les notes
    for r in tables["relationships"]:
        if r.get("relationship_status") != "confirmed":
            continue
        parent, child = r.get("parent_id"), r.get("child_id")
        if str(r.get("relationship_type") or "").lower() not in PARENT_TYPES:
            other_links[child].add(str(r.get("relationship_type")))
            continue
        if parent not in by_id or child not in by_id or parent == child:
            continue
        ctl, own = pct(r.get("control_pct")), pct(r.get("ownership_pct"))
        prev_ctl, prev_own = direct[child].get(parent, (None, None))
        direct[child][parent] = (keep_max(prev_ctl, ctl), keep_max(prev_own, own))

    def name(cid):
        return f"{by_id[cid].get('legal_name') or '?'} ({cid})"

    targetable = {cid for cid, c in by_id.items() if c.get("targetable") == "yes"}
    imported = set(targetable)
    if root_id:
        imported.add(root_id)

    def hubspot_parents(cid):
        """Parents importés de cid : {parent: (control_pct, ownership_pct, via)} et notes sur les chemins morts."""
        found, notes = {}, []

        def walk(node, first_hop, via, seen):
            for parent, pcts in direct.get(node, {}).items():
                # Le pourcentage retenu est celui du premier lien : la part que détient la holding sautée, par exemple
                hop = first_hop or pcts
                if parent in seen:
                    notes.append(f"cycle dans les liens de détention autour de {name(parent)}, à corriger dans relationships")
                    continue
                if parent in imported:
                    ctl, own, first_via = found.get(parent, (None, None, via))
                    found[parent] = (keep_max(ctl, hop[0]), keep_max(own, hop[1]), first_via)
                elif direct.get(parent):
                    walk(parent, hop, via + [name(parent)], seen | {parent})  # société non importée : on la saute
                else:
                    notes.append(f"{name(parent)} n'est pas importée et n'a pas de parent confirmé")

        walk(cid, None, [], {cid})
        return found, notes

    def primary_of(parents):
        if len(parents) == 1:
            return next(iter(parents))
        # control_pct départage, puis ownership_pct. Un critère ne compte que s'il est connu pour tous les parents.
        for index in (0, 1):
            values = {p: v[index] for p, v in parents.items()}
            if any(v is None for v in values.values()):
                continue
            ranked = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
            if ranked[0][1] > ranked[1][1]:
                return ranked[0][0]
        return None

    parents_of, notes_of, primary = {}, {}, {}
    for cid in imported:
        found, notes = hubspot_parents(cid)
        parents_of[cid] = found
        primary[cid] = primary_of(found) if found else None
        if cid == root_id and not found:
            note = "racine du groupe"
            if root_id not in targetable:
                note += ", importée pour relier les filiales (targetable = no)"
            notes = [note]
        elif not found and not notes:
            note = "aucun lien confirmé de détention ou de contrôle vers une société importée"
            if other_links.get(cid):
                note += f" (seulement {', '.join(sorted(other_links[cid]))} : parent direct à prouver)"
            notes = [note]
        elif len(found) > 1 and primary[cid] is None:
            notes.append("plusieurs parents sans majorité nette : pas de parent principal")
        notes_of[cid] = notes

    level = {}

    def get_level(cid, visiting=()):
        if cid in level:
            return level[cid]
        if cid in visiting:
            raise ValueError(
                f"participations croisées autour de {name(cid)} : des sociétés importées se détiennent mutuellement, "
                "l'ordre d'import est impossible. Garder le lien majoritaire en confirmed et passer l'autre "
                "dans notes ou en relationship_status non confirmé, puis relancer."
            )
        parents = parents_of[cid]
        level[cid] = 0 if not parents else 1 + max(get_level(p, visiting + (cid,)) for p in parents)
        return level[cid]

    company_rows, association_rows = [], []
    for cid in imported:
        c = by_id[cid]
        row = {"hubspot_level": get_level(cid), **{h: c.get(h) for h in headers["companies"]}}
        row.update({
            "hubspot_parent_count": len(parents_of[cid]),
            "hubspot_primary_parent_id": primary[cid],
            "hubspot_notes": " ; ".join(notes_of[cid]) or None,
        })
        company_rows.append(row)
        for parent, (ctl, own, via) in parents_of[cid].items():
            p = by_id[parent]
            association_rows.append({
                "child_level": level[cid],
                "child_company_id": cid,
                "child_legal_name": c.get("legal_name"),
                "child_siren": c.get("siren"),
                "parent_company_id": parent,
                "parent_legal_name": p.get("legal_name"),
                "parent_siren": p.get("siren"),
                "ownership_pct": fmt_pct(own),
                "control_pct": fmt_pct(ctl),
                "primary_parent": "yes" if parent == primary[cid] else "no",
                "via": " > ".join(via) or None,
            })
    company_rows.sort(key=lambda r: (r["hubspot_level"], str(r.get("legal_name") or "")))
    association_rows.sort(key=lambda r: (r["child_level"], str(r["child_legal_name"] or ""), r["primary_parent"] != "yes"))
    return company_rows, association_rows


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Prépare l'import HubSpot d'une cartographie de compte.")
    ap.add_argument("path", help="dossier de CSV ou fichier .xlsx")
    ap.add_argument("--root", help="company_id de la racine du groupe (sinon lu dans coverage.root_company_id)")
    ap.add_argument("--out-dir", help="dossier de sortie (défaut : à côté de l'entrée)")
    args = ap.parse_args()

    src = Path(args.path)
    if not src.exists():
        print(f"ERROR: fichier ou dossier introuvable: {src}")
        return 2
    try:
        tables, headers, fmt = load_tables(src)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 2

    # On ne prépare pas d'import sur une cartographie qui a des erreurs bloquantes
    errors, warnings = check(tables, headers, fmt)
    if errors:
        print("Cartographie invalide, import non préparé.")
        print_report(errors, warnings)
        return 1

    root_id = args.root or read_root(tables["coverage"])
    ids = {c.get("company_id") for c in tables["companies"]}
    if root_id and root_id not in ids:
        print(f"ERROR: la racine {root_id!r} n'existe pas dans companies")
        return 1

    try:
        company_rows, association_rows = build(tables, headers, root_id)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else (src if src.is_dir() else src.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    company_columns = ["hubspot_level"] + headers["companies"] + ["hubspot_parent_count", "hubspot_primary_parent_id", "hubspot_notes"]
    write_csv(out_dir / "hubspot_import.csv", company_columns, company_rows)
    write_csv(out_dir / "hubspot_associations.csv", ASSOCIATION_COLUMNS, association_rows)

    # Récapitulatif pour préparer l'import
    print(f"Écrit : {out_dir / 'hubspot_import.csv'} ({len(company_rows)} sociétés)")
    for lvl, n in sorted(Counter(r["hubspot_level"] for r in company_rows).items()):
        print(f"  niveau {lvl} : {n} société(s)")
    print(f"Écrit : {out_dir / 'hubspot_associations.csv'} ({len(association_rows)} liens société -> parent)")
    multi = [r for r in company_rows if r["hubspot_parent_count"] > 1]
    if multi:
        no_primary = sum(1 for r in multi if not r["hubspot_primary_parent_id"])
        print(f"  {len(multi)} société(s) à plusieurs parents, dont {no_primary} sans parent principal")
    if not root_id:
        print("  ⚠ racine non renseignée (coverage.root_company_id ou --root) : si elle n'est pas targetable, "
              "ses filiales directes n'auront pas de parent dans HubSpot")
    orphans = [r for r in company_rows if not r["hubspot_parent_count"] and r.get("company_id") != root_id]
    if orphans:
        print(f"  ⚠ {len(orphans)} société(s) sans parent en dehors de la racine :")
        for r in orphans:
            print(f"    - {r.get('legal_name')} ({r.get('company_id')}) : {r['hubspot_notes']}")
    domains = Counter(r.get("domain") for r in company_rows if r.get("domain"))
    shared = sorted(d for d, n in domains.items() if n > 1)
    if shared:
        print(f"  ⚠ {len(shared)} domaine(s) partagé(s) par plusieurs sociétés : {', '.join(shared)}")
        print("    HubSpot dédoublonne les sociétés sur le domaine à l'import : prendre le SIREN "
              "(propriété à valeur unique) comme clé, sinon ces sociétés seront fusionnées")
    no_siren = sum(1 for r in company_rows if not r.get("siren"))
    if no_siren:
        print(f"  ⚠ {no_siren} société(s) sans SIREN : prévoir une autre clé unique pour elles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
