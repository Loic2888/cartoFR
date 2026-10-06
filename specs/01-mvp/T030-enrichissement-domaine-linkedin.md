# T030 — Ajouter le domaine et la page LinkedIn des sociétés

**Story** : US6 (P3) · **Phase** : US6 · **Parallèle** : [P]
**Couvre** : FR-011 · P3
**Estimé** : 3 h

## Contexte
Prépare la prospection. **À préciser avant de commencer** : la source (recherche web, Cargo ou Basile) n'est pas tranchée (`needs-spec`).

## Périmètre
Enrichissement au moment de la mise à jour de la base, jamais pendant le calcul d'une carto.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/registre/enrichissement.py`
- `worker/tests/registre/test_enrichissement.py`

### Fonctionnement attendu
- Seulement pour les sociétés ciblables des groupes cartographiés

### Technologies
- Selon la source retenue

### Motifs d'architecture
Aucun appel extérieur pendant une carto (principe 3).

## Critères de succès
- [ ] **C1** : L'enrichissement tourne dans un travail `synchro` ou dédié, jamais dans `jobs/carto.py`
- [ ] **C2** : `rapport.md` donne la part des sociétés ciblables de LVMH qui ont un domaine

## Tests et validation

### Vérification manuelle
1. Enrichir LVMH et contrôler 10 domaines à la main

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T013
**Bloque** : —
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-011
- **ARCHI** : P3
