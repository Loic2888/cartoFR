# T032 — Retirer les scripts du prototype une fois la parité atteinte

**Story** : Transverse · **Phase** : Polish · **Parallèle** : séquentiel
**Couvre** : P5
**Estimé** : 1-2 h

## Contexte
Tant que les scripts de la racine existent, il y a deux moteurs, et la règle « la racine fait foi » devient fausse.

## Périmètre
Supprimer les scripts racine devenus inutiles, mettre à jour CLAUDE.md (Structure, Commandes) et la copie du skill.

## Mise en œuvre

### Fichiers à créer ou modifier
- Scripts de la racine (`engine.py`, `brand_scan.py`, `build_*.py`, …) — à lister et à faire valider avant suppression
- `CLAUDE.md` — Structure et Commandes
- `skills/account-mapping/scripts/moteur_france/` — pointe vers le paquet

### Fonctionnement attendu
- Regarder avant de supprimer : liste annoncée à l'utilisateur

### Technologies
- —

### Motifs d'architecture
—

## Critères de succès
- [ ] **C1** : Aucun script de la racine n'est encore appelé par `worker/` ni par `infra/`
- [ ] **C2** : `CLAUDE.md` décrit la structure et les commandes du paquet, plus celles du prototype
- [ ] **C3** : La non-régression lancée depuis le paquet donne les scores de T024

## Tests et validation

### Vérification manuelle
1. Lancer la non-régression depuis un clone propre

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T024
**Bloque** : —
**Fichiers partagés avec** : `CLAUDE.md`

## Documentation
- **PRD** : —
- **ARCHI** : Arborescence
