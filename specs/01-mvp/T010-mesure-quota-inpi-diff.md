# T010 — Mesurer le quota réel de l'API diff de l'INPI

**Story** : US1 (P1) · **Phase** : US1 · **Parallèle** : [P]
**Couvre** : FR-001 · ADR-002
**Estimé** : 1-2 h

## Contexte
ADR-002 repose sur une hypothèse : l'API `/api/companies/diff` permet de suivre 15 000 à 20 000 formalités par jour. Il faut la vérifier avant d'écrire la synchro.

## Périmètre
Un client de `/api/companies/diff` avec reprise par `searchAfter`, et une mesure écrite.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/registre/inpi_diff.py` — client, pagination, reprise, gestion du 429
- `worker/scripts/mesure_quota_diff.py` — lecture d'une journée complète, comptage
- `ARCHI.md` — ADR-002 complété avec la mesure
- `rapport.md` — résultat daté

### Fonctionnement attendu
- Arrêt propre au 429, curseur sauvegardé

### Technologies
- httpx

### Motifs d'architecture
Les identifiants viennent de `.env` (garde-fou 5).

## Critères de succès
- [x] **C1** : `worker/cartofr/registre/inpi_diff.py` reprend une lecture à partir d'un curseur sauvegardé
- [x] **C2** : `rapport.md` contient, à la date de la mesure, le nombre de formalités lues avant le 429 et le volume d'une journée
- [x] **C3** : `ARCHI.md` ADR-002 dit si la voie API est retenue ou si l'on bascule sur le FTP

## Tests et validation

### Vérification manuelle
1. Lancer la mesure sur une journée récente, sans dépasser le quota en mode moteur

### Cas limites
- Quota atteint au milieu d'une page

## Dépendances

**À finir avant** : T001
**Bloque** : T011
**Fichiers partagés avec** : `ARCHI.md`, `rapport.md`

## Documentation
- **PRD** : FR-001
- **ARCHI** : ADR-002
