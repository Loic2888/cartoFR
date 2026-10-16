# T048 — Calculer chaque nuit la carto du pays

**Story** : US7 (P1) · **Phase** : 12, carto du pays · **Parallèle** : —
**Couvre** : FR-006 · FR-012 · SC-004 · SC-008 · SC-009 · G6 · R8 · P3 · P4 · P5 · P6 · P7
**Estimé** : 6 à 8 h

## Contexte
Cœur de US7. ARCHI (ADR-006, ADR-007) : un travail `pays` calcule tout le pays après chaque synchro réussie, et au plus tard 7 jours après le précédent, dans `pays.duckdb` sur le worker.

## Périmètre
Les étapes du travail `pays` (ARCHI, « Carto du pays ») :
1. l'arbre (T045), recalculé s'il le faut ;
2. la correspondance de tous les documents déposés (T046) ;
3. le moteur, tête seule + périmètre, pour chaque groupe à document ;
4. *(le traitement mutualiste viendra avec T049)* ;
5. les arbres qu'aucun groupe ne réclame deviennent leurs propres groupes : preuve « Mandat au registre : <rôle> », confiance A. Un sommet entrepreneur individuel n'est jamais une tête : le groupe est présenté par sa plus grande société, la tête est dite « personne physique, non affichée » ;
6. le départage (T047) ;
7. l'écriture de `pays.duckdb` à côté, puis le renommage, et une ligne `pays` dans `mises_a_jour`.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/pays/calcul.py` : les étapes, et `python -m cartofr.pays.calcul` pour le lancer à la main
- `worker/cartofr/pays/schema.py` : `pays_groupes`, `pays_societes` (ARCHI, tableau « La carto du pays »)
- `worker/cartofr/jobs/pays.py`, `worker/cartofr/jobs/__init__.py` : le travail `pays`
- `worker/cartofr/travaux.py` : insertion du travail après une synchro réussie, et au plus tard 7 jours après le dernier
- `worker/tests/pays/` : mini-registres et documents inventés
- `worker/scripts/mesure_pays.py` : la mesure sur le registre réel
- `rapport.md`

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G6 Aucun nom de personne | ⚠️ | Aucune colonne de personne. Condition : un sommet entrepreneur individuel n'est jamais tête affichée, ni par son nom ni par son SIREN (C3) |
| R8 Tests | ✅ | Chaque étape a son test sur mini-registre |
| P3 Aucun appel extérieur | ✅ | Registre et documents déjà déposés |
| P4 Fermer, jamais effacer | ✅ | `pays.duckdb` est dérivé, remplacé à chaque calcul, jamais une source |
| P5 Pas de régression silencieuse | ⚠️ | Les cartos de LVMH et VINCI dans `pays.duckdb` égalent celles de la non-régression `--perimetre --sans-reglages` (C4) |
| P6 Le registre ne quitte pas le worker | ✅ | `pays.duckdb` reste sur le worker |
| FR-003 Dernier état valide | ✅ | Écriture à côté puis renommage ; un échec laisse le fichier précédent (C5) |

## Critères de succès
- [ ] **C1** : sur un mini-registre, chaque société active est soit dans exactement un groupe de `pays_societes`, soit absente (son propre groupe) ; un groupe à document recolle les arbres de ses sociétés inscrites ; un arbre non réclamé est son propre groupe avec la preuve du rôle (tests)
- [ ] **C2** : le travail est inséré après chaque synchro réussie, et au plus tard 7 jours après le dernier calcul réussi, même sans synchro (tests de planification)
- [ ] **C3** : un arbre dont le sommet est un entrepreneur individuel n'a jamais ce SIREN comme tête ; aucun nom de personne dans `pays.duckdb` ni dans le journal (tests)
- [ ] **C4** : sur le registre réel, les groupes de LVMH et VINCI dans `pays.duckdb` contiennent les mêmes sociétés que `non_regression.py --perimetre --sans-reglages` (142/172 et 836/1 007 au 2026-10-16)
- [ ] **C5** : un calcul qui échoue laisse le `pays.duckdb` précédent et une ligne `echec` dans `mises_a_jour` ; un succès écrit une ligne `succes` avec le nombre de groupes et de sociétés rangées (tests)
- [ ] **C6** : `mesure_pays.py` sur le registre réel relève la durée totale (cible : moins d'une heure pour les documents déposés), la mémoire au plus, le nombre de groupes et la part des sociétés actives rangées (SC-008, première moitié : 100 %). Chiffres dans `rapport.md`

## Dépendances
**À finir avant** : T045, T046, T047
**Suivies de** : T049, T050, T052
**Fichiers partagés avec** : `jobs/__init__.py` (T008, T013, T021, T025), `travaux.py` (T013)
