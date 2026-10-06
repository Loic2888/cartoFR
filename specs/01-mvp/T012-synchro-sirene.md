# T012 — Appliquer les changements de SIRENE au registre

**Story** : US1 (P1) · **Phase** : US1 · **Parallèle** : [P]
**Couvre** : FR-001 · SC-003
**Estimé** : 2-3 h

## Contexte
Les noms, adresses, effectifs et statuts viennent de SIRENE. Les marques et les adresses du moteur en dépendent.

## Périmètre
Lecture de l'API Sirene par date de dernier traitement, mise à jour de `societes`, `etablissements` et `sieges`.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/registre/synchro_sirene.py`
- `worker/tests/registre/test_synchro_sirene.py`
- `worker/tests/fixtures/sirene/` — réponses d'API générées

### Fonctionnement attendu
- Pagination par curseur, 30 requêtes par minute au plus
- `non_diffusible` mis à jour

### Technologies
- httpx, DuckDB

### Motifs d'architecture
Mêmes règles que la synchro RNE : transaction, fermeture.

## Critères de succès
- [ ] **C1** : `test_synchro_sirene.py` vérifie création, modification et cessation d'une société
- [ ] **C2** : `test_synchro_sirene.py` vérifie le passage d'une société en non diffusible
- [ ] **C3** : Le client respecte 30 requêtes par minute (test avec horloge simulée)

## Tests et validation

### Vérification manuelle
1. Appliquer une journée réelle sur une copie du registre

### Cas limites
- Société devenue non diffusible

## Dépendances

**À finir avant** : T007
**Bloque** : T013
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-001
- **ARCHI** : Le worker
