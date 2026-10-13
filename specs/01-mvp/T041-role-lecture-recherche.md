# T041 — Donner au service recherche un rôle Postgres en lecture seule

**Story** : transverse · **Phase** : Finitions · **Parallèle** : —
**Couvre** : R7 · G5 · P6
**Estimé** : 2 h

## Contexte
Trouvé à T029 (2026-10-08) : pour l'export du skill, le service `recherche` lisait les cartos avec le rôle `postgres`, qui contourne RLS. L'isolation entre organisations ne tenait que par le filtre `organisation_id` écrit dans ses requêtes, alors que la règle produit 7 la veut au niveau de la base. À faire avant le déploiement (T005).

## Périmètre
Un rôle dédié, en lecture seule, limité aux tables de l'export, sans contournement de RLS, et des politiques qui ne lui montrent que l'organisation déclarée pour chaque requête.

## Mise en œuvre

### Fichiers à créer ou modifier
- `supabase/migrations/0006_role_recherche.sql` — rôle `cartofr_recherche`, fonction `organisation_de_la_requete()`, droits, politiques RLS
- `worker/cartofr/api_recherche.py` — déclare l'organisation pour la transaction de l'export
- `infra/docker-compose.yml`, `infra/generer-secrets.sh`, `infra/appliquer-migrations.sh`, `infra/README.md`, `.env.example` — `RECHERCHE_DB_PASSWORD`
- `worker/tests/test_role_recherche.py`
- `ARCHI.md`, `rapport.md`

### Fonctionnement attendu
- `cartofr_recherche` : ni superutilisateur, ni contournement de RLS, ni création de rôles ou de bases ; transactions en lecture seule par défaut
- Lecture de `groupes`, `reglages`, `cartos`, `carto_societes` seulement ; aucune autre table, aucune écriture
- Politiques RLS : ne montrent que les lignes de l'organisation déclarée par `set_config('cartofr.organisation', '<uuid>', true)` ; rien sans déclaration
- Mot de passe hors du code (garde-fou 5) : généré dans `infra/.env`, posé par `appliquer-migrations.sh`, passé à psql par l'environnement du conteneur
- Les requêtes de l'export gardent leur filtre `organisation_id` : deux barrières

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| R7 Isolation multi-tenant | ✅ | Isolation de la recherche tenue par RLS, plus seulement par le code (tests) |
| G5 Secrets | ✅ | Aucun mot de passe dans la migration ni dans le code ; nom seul dans `.env.example` |
| P6 Le registre ne quitte pas le worker | ➖ | Ne touche pas au registre |

## Critères de succès
- [x] **C1** : le rôle n'a aucun privilège dangereux et ouvre ses transactions en lecture seule (test)
- [x] **C2** : sans organisation déclarée, il ne voit rien ; avec A, il ne voit que A, même quand la requête demande B (test)
- [x] **C3** : il ne lit aucune autre table et n'écrit nulle part (tests)
- [x] **C4** : la route d'export marche avec ce rôle : 200 pour l'organisation de la carto, 404 pour une autre (test)
- [x] **C5** : sur une base neuve, le mot de passe se pose comme dans le script, et une vraie connexion avec le rôle est en lecture seule et ne voit rien sans déclaration

## Dépendances

**À finir avant** : T029
**Bloque** : T005 (à faire avant le déploiement)
