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

for f in "${fichiers[@]}"; do
  if [ ! -f "$f" ]; then
    echo "Fichier introuvable : $f" >&2
    exit 1
  fi
  echo "Migration : $f"
  docker compose -f infra/docker-compose.yml exec -T db \
    psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q -1 -f - < "$f"
done

echo "Migrations appliquées : ${#fichiers[@]}."
