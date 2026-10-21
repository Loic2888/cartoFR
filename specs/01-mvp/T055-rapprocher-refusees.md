# T055 — Rapprocher les lignes refusées par des règles écrites

**Story** : US7 (P1) · **Phase** : 12, carto du pays · **Parallèle** : —
**Couvre** : FR-013 · SC-001 · SC-008 · R8 · P1 · P3 · P5
**Estimé** : 1 jour

## Contexte
Au dépôt de T054 (2026-10-21), 1 156 des 3 441 lignes des listes du CAC 40 sont refusées : 876 introuvables, 280 homonymes. La correspondance cherche déjà dans tous les noms et sigles des 13 M d'unités légales du registre : une ligne refusée n'est pas une société absente. C'est un nom écrit autrement que la raison sociale, un fonds sans SIREN, une société fermée depuis, ou un nom pollué par la mise en page. Décision de Loïc du 2026-10-21 : d'abord des règles écrites, mesurées une à une ; ensuite, on décide s'il faut une table de correspondance alimentée par recherche web pour le reste.

## Périmètre
- Étape 6 de la correspondance, pour les seules lignes encore introuvables : `fonds` et `fermee` (refus expliqués), `compacte`, `usuelle`, `debut` (retenues).
- Candidats en plus à l'extraction : le nom sans son sigle final pour les formats texte de T054, les deux côtés d'un nom et de son sigle séparés par un tiret. Une rangée BNP d'un autre pays termine le nom en cours.
- Mesure par règle sur les 23 documents de T054 et sur LVMH, VINCI et CMAF ; relecture à la main de chaque ligne gagnée ; redépôt.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/perimetre/correspondance.py` : étape 6
- `worker/cartofr/perimetre/extraction.py` : candidats sans sigle, côtés du tiret, rangée BNP étrangère, `MOTIF_FONDS`
- `worker/cartofr/perimetre/deposer.py` : nouvelles raisons dans le compte rendu
- `worker/tests/perimetre/test_rapprochement_t055.py` (nouveau), `test_formats_t054.py`, `test_correspondance.py`, `worker/tests/moteur/fabrique.py` (dénomination usuelle)
- `rapport.md`

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| P1 L'IA ne décide pas | ✅ | Règles écrites, aucune IA ni recherche web |
| P3 Aucun appel extérieur | ✅ | Le registre local seul |
| P5 Pas de régression silencieuse | ✅ | Les anciennes retenues ne changent pas (étape 6 sur les introuvables seuls) ; LVMH, VINCI et CMAF comparés ligne à ligne ; non-régression inchangée |
| R8 Tests | ✅ | Un test par règle, et un par erreur trouvée à la relecture |
| G6 Aucun nom de personne | ✅ | Seuls les noms de sociétés sont lus, jamais `dirigeants_personnes` |

## Critères de succès
- [x] **C1** : chaque règle a sa mesure (lignes gagnées sur les 23 documents, sur LVMH, VINCI et CMAF) dans `rapport.md`
- [x] **C2** : chaque ligne gagnée est relue ; une règle qui retient une mauvaise société est resserrée, avec un test qui échouait avant
- [x] **C3** : aucune ligne retenue sous T054 n'est perdue ; non-régression inchangée
- [x] **C4** : la nouvelle mesure des 23 documents est dans `rapport.md` ; pas de redépôt, les documents sont les mêmes et la correspondance se refait à chaque carto

## Dépendances
**À finir avant** : T054
**Suivies de** : T048 (recalcul de la carto du pays) ; table de correspondance par recherche web, si Loïc la décide
**Fichiers partagés avec** : `perimetre/correspondance.py` (T042, T046, T053), `perimetre/extraction.py` (T054)
