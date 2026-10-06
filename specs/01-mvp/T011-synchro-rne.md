# T011 — Appliquer les changements du RNE au registre

**Story** : US1 (P1) · **Phase** : US1 · **Parallèle** : [P]
**Couvre** : FR-001 · FR-002 · SC-003 · P4
**Estimé** : 3 h

## Contexte
Le cœur de US1 : nouveaux liens ouverts, liens disparus fermés, sociétés créées ou radiées.

## Périmètre
Une fonction qui prend les formalités modifiées d'une période et met le registre à jour dans une transaction.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/registre/synchro_rne.py`
- `worker/cartofr/registre/formalite.py` — lecture d'une formalité (logique reprise de `build_links.py`)
- `worker/tests/registre/test_synchro_rne.py`
- `worker/tests/fixtures/rne/` — formalités **générées** (aucun vrai nom de personne)

### Fonctionnement attendu
- Un lien absent de la nouvelle formalité d'une société reçoit `fin`
- Aucun `DELETE`
- Échec : rollback, état précédent conservé, ligne `echec` dans `mises_a_jour`

### Technologies
- DuckDB, transactions

### Motifs d'architecture
Fermer, jamais effacer (principe 4).

## Critères de succès
- [ ] **C1** : `test_synchro_rne.py` vérifie qu'un nouveau lien est ouvert avec sa date de début
- [ ] **C2** : `test_synchro_rne.py` vérifie qu'un lien disparu est fermé et non supprimé
- [ ] **C3** : `test_synchro_rne.py` vérifie qu'une erreur en cours de lot laisse le registre inchangé
- [ ] **C4** : `grep -ri "delete" worker/cartofr/registre/synchro_rne.py` ne trouve aucun `DELETE` SQL
- [ ] **C5** : Les fixtures de `worker/tests/fixtures/rne/` ne contiennent que des noms inventés

## Tests et validation

### Vérification manuelle
1. Appliquer une journée réelle sur une copie du registre et compter les liens ouverts et fermés

### Cas limites
- Société radiée
- Formalité invalide

## Dépendances

**À finir avant** : T007, T010
**Bloque** : T013
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-001, FR-002
- **ARCHI** : Le worker, ADR-002
