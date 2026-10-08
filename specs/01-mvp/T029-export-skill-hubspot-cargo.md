# T029 — Exporter les 6 tables du skill account-mapping

**Story** : US5 (P3) · **Phase** : US5 · **Parallèle** : [P]
**Couvre** : FR-010
**Estimé** : 2-3 h

## Contexte
Le client importe le résultat dans HubSpot ou Cargo sans retraitement.

## Périmètre
Export des 6 tables du skill depuis une carto, à partir de `to_skill_tables.py`.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/exports/skill.py` — depuis `to_skill_tables.py`
- `worker/cartofr/api_recherche.py` — route interne `/export/skill/{carto}`
- `web/app/(app)/groupes/[id]/cartos/[cartoId]/export-skill/route.ts`
- `worker/tests/exports/test_skill.py`

### Fonctionnement attendu
- Fichiers d'import, pas de poussée directe dans le CRM (hors V1)

### Technologies
- —

### Motifs d'architecture
—

## Critères de succès
- [x] **C1** : La validation du skill passe avec 0 erreur sur les exports LVMH, VINCI et CMAF
- [x] **C2** : `test_skill.py` vérifie l'absence de nom de personne dans les 6 tables

> 2026-10-08 : C1 mesuré sur le registre réel (`test_registre_reel_export_valide_et_sans_personne`,
> 0 erreur pour les trois groupes). La vérification manuelle (import dans un HubSpot de test)
> reste à faire par un humain.

## Tests et validation

### Vérification manuelle
1. Importer l'export LVMH dans un HubSpot de test

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T019, T021
**Bloque** : —
**Fichiers partagés avec** : `worker/cartofr/api_recherche.py` (T019)

## Documentation
- **PRD** : FR-010
- **ARCHI** : Arborescence
