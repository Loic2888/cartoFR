# T025 — Faire proposer les réglages par l'IA

**Story** : US3 (P2) · **Phase** : US3 · **Parallèle** : séquentiel
**Couvre** : FR-008 · P1 · R5
**Estimé** : 3 h

## Contexte
Écrire les réglages d'un groupe neuf prend du temps. L'IA propose, l'humain valide.

## Périmètre
Type de travail `proposition` : lecture du site et du rapport annuel, proposition sourcée, enregistrée comme version non validée.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/ia/proposition.py`
- `worker/cartofr/jobs/proposition.py`
- `worker/cartofr/jobs/__init__.py` — enregistrement du type
- `worker/tests/ia/test_proposition.py` — API simulée

### Fonctionnement attendu
- Chaque marque porte sa source (URL)
- Marque avec homonymes au registre rangée en ambiguë
- Aucun nom de personne dans le prompt

### Technologies
- SDK `anthropic`, recherche web

### Motifs d'architecture
L'IA ne décide jamais (principe 1).

## Critères de succès
- [ ] **C1** : La proposition est enregistrée sans `valide_le` (test)
- [ ] **C2** : `test_proposition.py` vérifie qu'aucun nom de `dirigeants_personnes` n'entre dans le prompt
- [ ] **C3** : Une marque qui a des homonymes au registre est rangée en ambiguë (test)

## Tests et validation

### Vérification manuelle
1. Proposer les réglages d'un groupe connu et comparer à `config/`

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T020, T021
**Bloque** : T026
**Fichiers partagés avec** : `worker/cartofr/jobs/__init__.py` (T008, T013, T021)

## Documentation
- **PRD** : FR-008
- **ARCHI** : IA (P2)
