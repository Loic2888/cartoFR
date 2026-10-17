# T052 — Mesurer la carto du pays : justesse sans correction, fraîcheur, couverture

**Story** : US7 et US2 (P1) · **Phase** : 12, carto du pays · **Parallèle** : [P] avec T050
**Couvre** : SC-001 · SC-008 · SC-009 · P5
**Estimé** : 3 à 4 h

## Contexte
Le PRD du 2026-10-16 juge la carto sans correction (SC-001), demande que tout le pays soit couvert avant la mise en ligne (SC-008) et que chaque carto ait 7 jours de retard au plus (SC-009). Il faut le mesurer depuis `pays.duckdb`, pas depuis un calcul à part.

## Périmètre
- `non_regression.py --depuis-pays` : lit les groupes de LVMH, VINCI et CMAF dans `pays.duckdb`, avec les seuils de SC-001 (LVMH ≥ 154/172, VINCI ≥ 813/1 007, CMAF ≥ 43/52, les seuils exacts de la non-régression derrière « 90, 81 et 83 % » ; « en plus » non inscrits au document ≤ 16 et ≤ 193). Ces seuils sont la cible du PRD, pas l'état du jour : la commande échoue tant qu'ils ne sont pas tenus.
- Le contrôle hebdomadaire de fraîcheur (T015) vérifie aussi la date des données de la carto du pays : 7 jours au plus.
- `mesure_couverture.py` : part des sociétés actives rangées, et, à partir d'une liste des sociétés cotées à Paris (CSV fourni par Loïc, hors git), les groupes cotés avec et sans document.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/scripts/non_regression.py`
- `worker/cartofr/registre/fraicheur.py`
- `worker/scripts/mesure_couverture.py` (nouveau)
- tests worker
- `rapport.md`

## Critères de succès
- [ ] **C1** : `--depuis-pays` mesure les trois groupes dans `pays.duckdb` avec les seuils de SC-001, et rend 1 tant qu'un seuil manque (tests sur un `pays.duckdb` inventé)
- [ ] **C2** : le contrôle de fraîcheur signale une carto du pays de plus de 7 jours, comme un retard du registre (test)
- [ ] **C3** : `mesure_couverture.py` rend la part des sociétés actives rangées et la liste des groupes cotés sans document ; chiffres du jour dans `rapport.md`

## Dépendances
**À finir avant** : T048
**Fichiers partagés avec** : `non_regression.py` (T016, T021, T024, T043), `fraicheur.py` (T015)
