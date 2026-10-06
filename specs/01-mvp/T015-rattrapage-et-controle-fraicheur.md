# T015 — Rattraper le registre et contrôler la fraîcheur

**Story** : US1 (P1) · **Phase** : US1 · **Parallèle** : séquentiel
**Couvre** : SC-003
**Estimé** : 2 h

## Contexte
Le stock date du 2026-03-04. Il faut rattraper sept mois, puis prouver qu'on tient 7 jours.

## Périmètre
Rattrapage initial sur le serveur, et un script de contrôle hebdomadaire de 10 changements tirés au hasard.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/scripts/controle_fraicheur.py`
- `rapport.md` — résultat du rattrapage et du premier contrôle

### Fonctionnement attendu
- Tirage de 10 changements publiés dans les 7 derniers jours, vérifiés dans le registre

### Technologies
- API INPI, API Sirene

### Motifs d'architecture
—

## Critères de succès
- [ ] **C1** : `worker/scripts/controle_fraicheur.py` rend le nombre de changements trouvés sur 10
- [ ] **C2** : `rapport.md` contient, datés, le rattrapage terminé et un premier contrôle à 10/10

## Tests et validation

### Vérification manuelle
1. Lancer le contrôle une semaine de suite

### Cas limites
- Aucun propre à cette tâche

## Dépendances

**À finir avant** : T005, T013
**Bloque** : T024
**Fichiers partagés avec** : `rapport.md`

## Documentation
- **PRD** : SC-003
- **ARCHI** : ADR-002
