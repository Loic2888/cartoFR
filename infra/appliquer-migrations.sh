#!/usr/bin/env bash
# Applique les migrations SQL de supabase/migrations/ à la base locale (service db).
#
# Usage, depuis la racine du dépôt, la stack lancée (voir infra/README.md) :
#   bash infra/appliquer-migrations.sh                                   # toutes, dans l'ordre
#   bash infra/appliquer-migrations.sh supabase/migrations/0002_x.sql    # seulement celles-ci
#   bash infra/appliquer-migrations.sh supabase/seed/reglages_depart.sql # données de départ (rejouables)
#
# Chaque fichier passe dans une seule transaction : une erreur annule ce
# fichier entier et arrête le script. Aucun suivi des migrations déjà jouées :
# rejouer une migration échoue bruyamment (« already exists ») sans rien
# modifier. Sur une base existante, ne passer que les nouveaux fichiers.
# psql tourne dans le conteneur, en socket local : aucun mot de passe affiché.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "$#" -gt 0 ]; then
  fichiers=("$@")
else
  fichiers=(supabase/migrations/*.sql)
fi

# Le seed calcule les empreintes des familles exclues (garde-fou 6) avec la clé
# CARTOFR_CLE_EMPREINTE d'infra/.env, passée à psql sans être affichée.
cle=""
if [ -f infra/.env ]; then
  cle="$(grep -E '^CARTOFR_CLE_EMPREINTE=' infra/.env | head -1 | cut -d= -f2- || true)"
fi

for f in "${fichiers[@]}"; do
  if [ ! -f "$f" ]; then
    echo "Fichier introuvable : $f" >&2
    exit 1
  fi
  echo "Migration : $f"
  options=()
  case "$f" in
    supabase/seed/*)
      if [ -z "$cle" ]; then
        echo "CARTOFR_CLE_EMPREINTE absente d'infra/.env : le seed a besoin de cette clé." >&2
        exit 1
      fi
      options=(-e "PGOPTIONS=-c cartofr.cle_empreinte=$cle")
      ;;
  esac
  docker compose -f infra/docker-compose.yml exec -T "${options[@]}" db \
    psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q -1 -f - < "$f"
done

# Mot de passe du rôle en lecture seule du service recherche (migration 0006, T041),
# lu dans infra/.env et passé à psql par l'environnement du conteneur, jamais affiché
# ni écrit dans la ligne de commande. Rejouable : il ne fait que reposer le mot de passe.
mdp_recherche=""
if [ -f infra/.env ]; then
  mdp_recherche="$(grep -E '^RECHERCHE_DB_PASSWORD=' infra/.env | head -1 | cut -d= -f2- || true)"
fi
role_present="$(docker compose -f infra/docker-compose.yml exec -T db \
  psql -U postgres -d postgres -tAq -c "select 1 from pg_roles where rolname = 'cartofr_recherche'")"
if [ "$role_present" = "1" ]; then
  if [ -z "$mdp_recherche" ]; then
    echo "RECHERCHE_DB_PASSWORD absent d'infra/.env : le service recherche ne pourra pas se connecter." >&2
    echo "Ajoutez la ligne (par ex. RECHERCHE_DB_PASSWORD=\$(openssl rand -hex 24)) puis relancez ce script." >&2
    exit 1
  fi
  printf '%s\n' "alter role cartofr_recherche with login password :'mdp';" |
    docker compose -f infra/docker-compose.yml exec -T -e MDP="$mdp_recherche" db \
      sh -c 'psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q -v mdp="$MDP" -f -'
  echo "Rôle cartofr_recherche : mot de passe posé."
fi

echo "Migrations appliquées : ${#fichiers[@]}."
