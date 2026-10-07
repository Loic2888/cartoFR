"""Génère supabase/seed/reglages_depart.sql depuis config/*.json (T018).

But : charger les réglages historiques des groupes (LVMH, VINCI, CMAF) dans la
base de l'app, comme version 1 validée de chaque groupe de l'organisation
Youno. Le contenu est recopié tel quel depuis config/<g>.json : on régénère
le seed au lieu de le corriger à la main.

Usage (depuis la racine du dépôt) :
    .venv/bin/python worker/scripts/generer_seed_reglages.py          # écrit le fichier
    .venv/bin/python worker/scripts/generer_seed_reglages.py --check  # échoue s'il n'est pas à jour

Entrées : config/*.json (clés `groupe` et `tete` obligatoires).
Sortie : supabase/seed/reglages_depart.sql, idempotent (on conflict do nothing),
à appliquer après les migrations, dans une transaction (psql -1).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CONFIG = RACINE / "config"
SORTIE = RACINE / "supabase" / "seed" / "reglages_depart.sql"
ORGANISATION = "Youno"

ENTETE = f"""\
-- Réglages de départ : les réglages historiques du prototype (config/*.json),
-- chargés comme version 1 validée de chaque groupe de l'organisation
-- {ORGANISATION} (T018, C4 ; principe 2).
--
-- FICHIER GÉNÉRÉ par worker/scripts/generer_seed_reglages.py : ne pas le
-- modifier à la main, modifier config/*.json puis relancer le script.
--
-- Ces versions ont été validées par un humain du temps du prototype, hors de
-- l'app : origine 'depart', valide_le posé, valide_par nul (voir le
-- commentaire de public.reglages dans 0002_cartos.sql).
--
-- Idempotent : rejouer ce fichier ne change rien. Il crée l'organisation
-- {ORGANISATION} si aucune n'existe, et sinon prend la plus ancienne de ce nom.
-- À jouer après les migrations, en une transaction : psql -v ON_ERROR_STOP=1 -1 -f
"""


def _litteral(texte: str) -> str:
    """Chaîne SQL entre apostrophes, apostrophes doublées."""
    return "'" + texte.replace("'", "''") + "'"


def _dollar(texte: str) -> str:
    """Chaîne SQL entre dollars, avec une étiquette absente du texte."""
    n = 0
    while f"$r{n}$" in texte:
        n += 1
    return f"$r{n}${texte}$r{n}$"


def charger_configs(dossier: Path = CONFIG) -> list[tuple[str, dict[str, object]]]:
    """Rend (nom du fichier sans extension, contenu) pour chaque config, triés par nom."""
    configs: list[tuple[str, dict[str, object]]] = []
    for chemin in sorted(dossier.glob("*.json")):
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        tete = str(contenu.get("tete", ""))
        if not re.fullmatch(r"[0-9]{9}", tete):
            raise ValueError(f"{chemin.name} : `tete` n'est pas un SIREN à 9 chiffres")
        if not str(contenu.get("groupe", "")).strip():
            raise ValueError(f"{chemin.name} : `groupe` est vide")
        configs.append((chemin.stem, contenu))
    if not configs:
        raise ValueError(f"aucune config dans {dossier}")
    return configs


def generer(configs: list[tuple[str, dict[str, object]]]) -> str:
    """Rend le texte SQL du seed."""
    org = _litteral(ORGANISATION)
    blocs = [
        ENTETE,
        f"""insert into public.organisations (nom)
select {org}
where not exists (select 1 from public.organisations where nom = {org});
""",
    ]
    for fichier, contenu in configs:
        tete = _litteral(str(contenu["tete"]))
        nom = _litteral(str(contenu["groupe"]))
        json_texte = json.dumps(contenu, ensure_ascii=False, indent=2)
        blocs.append(
            f"""-- {fichier} : config/{fichier}.json
with org as (
  select id from public.organisations where nom = {org} order by cree_le, id limit 1
)
insert into public.groupes (organisation_id, tete_siren, nom)
select org.id, {tete}, {nom} from org
on conflict (organisation_id, tete_siren) do nothing;

with g as (
  select g.id, g.organisation_id
  from public.groupes g
  where g.tete_siren = {tete}
    and g.organisation_id = (
      select id from public.organisations where nom = {org} order by cree_le, id limit 1
    )
)
insert into public.reglages (groupe_id, organisation_id, version, contenu, origine, valide_le)
select g.id, g.organisation_id, 1, {_dollar(json_texte)}::jsonb, 'depart', now() from g
on conflict (groupe_id, version) do nothing;
"""
        )
    return "\n".join(blocs)


def main(argv: list[str]) -> int:
    texte = generer(charger_configs())
    if "--check" in argv:
        actuel = SORTIE.read_text(encoding="utf-8") if SORTIE.exists() else ""
        if actuel != texte:
            print(f"{SORTIE.relative_to(RACINE)} n'est pas à jour : relancer ce script.", file=sys.stderr)
            return 1
        print(f"{SORTIE.relative_to(RACINE)} est à jour.")
        return 0
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(texte, encoding="utf-8")
    print(f"Écrit : {SORTIE.relative_to(RACINE)} ({len(texte)} caractères).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
