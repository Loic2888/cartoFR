# T053 — Retrouver 90 % de LVMH sans correction

**Story** : US7 (P1) · **Phase** : 12, carto du pays · **Parallèle** : —
**Couvre** : SC-001 · R8 · P1 · P5
**Estimé** : 4 à 8 h, dont l'analyse

## Contexte
Au 2026-10-16, sans correction, LVMH est à 142/172 (83 %) pour une cible de 154/172 (« 90 % », PRD SC-001, seuil exact de la non-régression). VINCI (836, cible 813) et CMAF (T049) suivent leur propre chemin. Décision de Loïc : on ne baisse pas la cible, on cherche d'où vient le manque. Le document LVMH 2024 ne liste que les principales sociétés (232 lignes en France), et la correspondance en refuse 62 (homonymes, introuvables).

## Périmètre
1. Ranger les 30 sociétés manquées par cause : absente du document, ligne refusée (laquelle, pourquoi), inscrite mais filiales non descendues, autre. Chiffres dans `rapport.md`, dénominations de sociétés seulement.
2. Corriger les causes qui relèvent d'une règle écrite : correspondance plus souple sous confirmation du registre, autre format de liste, autre document publié par le groupe. Chaque changement de règle arrive avec ses tests, et se mesure sur LVMH, VINCI et CMAF.

## Mise en œuvre

### Fichiers à créer ou modifier
- selon l'analyse : `worker/cartofr/perimetre/`, `worker/cartofr/moteur/`
- tests correspondants
- `rapport.md`

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| R8 Tests | ✅ | Chaque règle changée arrive avec ses tests |
| P1 L'IA ne décide pas | ✅ | Seules des règles écrites décident |
| P5 Pas de régression silencieuse | ⚠️ | Non-régression des trois groupes, dans les deux modes, avant la PR (C3) |

## Critères de succès
- [x] **C1** : `rapport.md` range les sociétés de LVMH manquées sans correction par cause, avec leur nombre
- [x] **C2** : sans correction, LVMH ≥ 154/172, « en plus » non inscrits au document ≤ 16
- [x] **C3** : VINCI et CMAF ne baissent pas, dans les deux modes de la non-régression (sans correction, et avec les réglages de `config/`)

## Dépendances
**À finir avant** : T048 (mesure dans `pays.duckdb`), T052
**Fichiers partagés avec** : selon l'analyse ; `perimetre/correspondance.py` (T042, T046)
