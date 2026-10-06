# T017 — Tester chaque règle qui décide

**Story** : US2 (P1) · **Phase** : US2 · **Parallèle** : séquentiel
**Couvre** : R8 · FR-006
**Estimé** : 3 h

## Contexte
Règle produit 8 : filiale ou non, maison mère, confiance, ciblable arrivent avec leurs tests.

## Périmètre
Un jeu de tests sur de petits registres fabriqués, une règle à la fois.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/tests/moteur/fabrique.py` — construit un mini-registre en mémoire
- `worker/tests/moteur/test_regles.py`

### Fonctionnement attendu
- Cas : marque sûre, marque ambiguë sans deuxième preuve, mandat, GIE 100 % groupe, co-entreprise, adresse seule (refusée), holding familiale exclue, comité d'entreprise, ciblable Oui/Non

### Technologies
- pytest

### Motifs d'architecture
Tests sur noms inventés seulement (R6).

## Critères de succès
- [ ] **C1** : `test_regles.py` couvre confiance A, B et C
- [ ] **C2** : `test_regles.py` couvre le choix de la maison mère directe
- [ ] **C3** : `test_regles.py` couvre ciblable Oui et Non avec la raison
- [ ] **C4** : `test_regles.py` vérifie que l'adresse seule ne fait pas entrer une société
- [ ] **C5** : `test_regles.py` vérifie qu'une marque ambiguë exige une deuxième preuve

## Tests et validation

### Vérification manuelle
1. `pytest worker/tests/moteur`

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T016
**Bloque** : —
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-006, R8
- **ARCHI** : Principe 7
