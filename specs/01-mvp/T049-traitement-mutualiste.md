# T049 — Ranger les groupes mutualistes sans mêler leurs fédérations

**Story** : US7 (P1) · **Phase** : 12, carto du pays · **Parallèle** : —
**Couvre** : FR-014 · SC-001 · R8 · P1 · P5 · P7
**Estimé** : 5 à 8 h, dont la mesure

## Contexte
Mesure du 2026-10-15 : les arbres du Crédit Mutuel mêlent plusieurs fédérations (Maine-Anjou et Basse-Normandie, hors CMAF, avec des caisses de CMAF). Le 2026-10-16, CMAF tombe à 1/52 sans correction : pas de document, pas de traitement à part. Décision de Loïc : traitement à part, dans la V1. La règle n'est pas encore connue (PRD, questions ouvertes).

## Périmètre
1. **Mesurer d'abord**, en lecture seule, sur le registre et la référence CMAF : comment les caisses locales, les caisses fédérales et les filiales de CMAF sont reliées entre elles, et à d'autres fédérations. Essayer au moins : le document d'enregistrement universel de CMAF comme périmètre (dépôt du PDF par Loïc, le site BFCM refuse le téléchargement automatique) ; la caisse fédérale comme tête, avec ses caisses locales par le rôle « membre » ; le nom de la fédération dans la dénomination.
2. Écrire la règle retenue, avec Loïc, dans le travail `pays` (étape 4), et ses tests.
3. Étendre la règle aux autres groupes mutualistes repérés pendant la mesure (BPCE, Crédit Agricole, Groupama…), ou dire pourquoi pas.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/pays/mutualiste.py` (nouveau), `worker/cartofr/pays/calcul.py` (étape 4)
- `worker/tests/pays/test_mutualiste.py`
- `worker/scripts/mesure_mutualiste.py` : la mesure, rejouable (références hors git)
- `rapport.md`

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G6 Aucun nom de personne | ✅ | Les administrateurs mutualistes sont des personnes : la règle ne les lit pas, ou seulement comme preuve interne, jamais en sortie |
| R8 Tests | ✅ | La règle arrive avec ses tests |
| P1 L'IA ne décide pas | ✅ | Règle écrite |
| P5 Pas de régression silencieuse | ⚠️ | LVMH et VINCI inchangés dans `pays.duckdb` (C3) |

## Critères de succès
- [ ] **C1** : `rapport.md` donne la mesure : pour chaque piste essayée, sociétés de la référence CMAF retrouvées, « en plus », et sociétés d'autres fédérations entrées à tort
- [ ] **C2** : la règle retenue est testée sur des mini-registres inventés : deux fédérations dans un même arbre sont séparées ; une caisse locale rejoint sa fédération
- [ ] **C3** : dans `pays.duckdb`, CMAF ≥ 43/52 (83 %, PRD SC-001), sans correction ; LVMH et VINCI inchangés
- [ ] **C4** : aucune société n'est dans deux groupes mutualistes (test)

## Dépendances
**À finir avant** : T048
**Préalable humain** : le document d'enregistrement universel 2024 de CMAF, déposé par Loïc
**Fichiers partagés avec** : `pays/calcul.py` (T048)
