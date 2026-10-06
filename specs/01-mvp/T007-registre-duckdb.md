# T007 — Construire `registre.duckdb` avec dates de début et de fin

**Story** : Socle · **Phase** : Foundational · **Parallèle** : [P]
**Couvre** : FR-002 · FR-003 · P4
**Estimé** : 2-3 h

## Contexte
Le registre sert à la synchro (US1) et au moteur (US2). Il remplace les parquets épars du prototype.

## Périmètre
Un fichier `registre.duckdb` construit depuis `data/rne_links/`, `data/sieges.parquet` et `data/unite_legale.parquet`, avec `debut` et `fin` sur les sociétés et les liens, et la table `mises_a_jour`.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/registre/schema.py` — création des tables
- `worker/cartofr/registre/construire.py` — chargement initial depuis les parquets
- `worker/cartofr/registre/journal.py` — écriture dans `mises_a_jour`
- `worker/tests/registre/test_construire.py`

### Fonctionnement attendu
- Colonnes `opposition_prospection` et `non_diffusible` (INSEE) sur `societes`
- `dirigeants_personnes` gardée pour le calcul seulement

### Technologies
- DuckDB

### Motifs d'architecture
Le registre ne quitte pas le worker (principe 6).

## Critères de succès
- [ ] **C1** : `python -m cartofr.registre.construire` produit `data/registre.duckdb`
- [ ] **C2** : Le nombre de liens actifs est égal à celui de `data/rne_links/liens.parquet` (1 644 581 au 2026-10-06)
- [ ] **C3** : `societes` et `liens` ont les colonnes `debut` et `fin`
- [ ] **C4** : `societes.non_diffusible` est renseignée depuis SIRENE
- [ ] **C5** : `worker/tests/registre/test_construire.py` passe sur un mini-jeu de parquets générés

## Tests et validation

### Vérification manuelle
1. Construire le registre complet et comparer les comptes aux parquets

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T001
**Bloque** : T011, T012, T016
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-002, FR-003
- **ARCHI** : Données §1
