# T045 — Construire l'arbre à une mère du registre

**Story** : US1 (P1) · **Phase** : 11, arbre du registre · **Parallèle** : —
**Couvre** : FR-001 · FR-003 · G6 · R8 · P1 · P4 · P6 · P7
**Estimé** : 4 à 6 h

## Contexte
Mesure du 2026-10-15 (`rapport.md`). Pour calculer un jour la carto de tout le pays, il faut d'abord découper le registre en groupes propres. Les blocs (toutes les sociétés reliées par un lien) ne marchent pas : un bloc géant mêle LVMH, VINCI et CMAF. Les arbres marchent : chaque société reçoit une seule mère, et on remonte jusqu'au sommet. Les gros arbres sont propres (80 à 85 % de leurs sociétés sont dans la référence) et aucun ne dépasse 1 333 sociétés.

## Périmètre
Le worker calcule, pour chaque société qui a une mère dans le registre, sa mère, le rôle qui l'y relie et son sommet. Il le range dans une table de `registre.duckdb`, recalculée après chaque synchro. Il ne touche pas au moteur. Aucune carto ne se sert de l'arbre dans cette tâche : le recollage par les listes publiées et la carto du pays viendront après une mise à jour de `PRD.md`, d'`ARCHI.md` et du principe 2.

Règle, mesurée le 2026-10-15 :
- **liens pris en compte** : liens actifs (`fin` vide) entre deux SIREN différents ;
- **rôles** : on garde ceux de la liste ci-dessous. Tout autre rôle est écarté, notamment les commissaires aux comptes (71, 72, 77) ;
- **parents écartés** : un parent qui a plus de 500 enfants par ses liens actifs, tous rôles comptés (gérants de défiscalisation, sociétés de gestion) n'est la mère de personne ;
- **choix de la mère** : celle du rôle le plus fort, dans cet ordre :
  1. 73 ;
  2. 51 et 30 ;
  3. 28, 29 et 131 ;
  4. 74 et 75 ;
  5. 53 ;
  6. 65 et 64 ;
  7. 11 ;
  8. 99.

  À rôle égal, le parent qui a le plus d'enfants l'emporte, puis le plus petit SIREN ;
- **sommet** : on remonte de mère en mère jusqu'à une société sans mère. Dans une boucle (A mère de B, B mère de A), le sommet est le plus petit SIREN de la boucle, pour toutes les sociétés qui y mènent, et la ligne est marquée `boucle`.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/registre/arbre.py` : la règle et le calcul de la table, plus un point d'entrée `python -m cartofr.registre.arbre`
- `worker/cartofr/registre/schema.py` : la table `arbre`
- `worker/cartofr/jobs/synchro.py` : recalcul après les sources du passage
- `worker/tests/registre/test_arbre.py` : mini-registres **inventés**
- `worker/scripts/mesure_arbre.py` : rejoue la mesure du 2026-10-15 (les références restent dans `basile/`, hors git)
- `rapport.md`

### Table
`arbre` : une ligne par société qui a une mère. Colonnes : `siren`, `mere`, `role_mere`, `sommet`, `profondeur` (1 pour un enfant direct du sommet), `boucle`. Une société absente de la table est son propre sommet. Aucune colonne de nom.

C'est une table dérivée, recalculée en entier depuis `liens`. L'historique reste dans `liens`, où rien n'est effacé (principe 4).

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G6 Aucun nom de personne | ⚠️ | La table ne porte que des SIREN et des codes de rôle, jamais un nom. `dirigeants_personnes` n'est pas lu. Un parent peut être une entreprise individuelle : son SIREN reste dans le worker. Condition : `mesure_arbre.py` n'affiche que des dénominations d'`unites_legales`, qui exclut la catégorie 1000 (C5) |
| R6 Aucune donnée client en dev | ✅ | Registre public. Les références Basile restent hors git et ne servent qu'à la mesure |
| R8 Tests sur la logique métier | ✅ | Choix de la mère, sommet et boucles arrivent avec leurs tests, cas limites compris (C1, C2) |
| P1 L'IA ne décide pas | ✅ | Aucune IA : règle écrite et reproductible |
| P2 Réglages validés par un humain | ➖ | Aucune carto ne se sert de l'arbre |
| P4 Fermer, jamais effacer | ⚠️ | La table est dérivée et remplacée à chaque calcul. Condition : elle ne devient jamais une source. Tout se recalcule depuis `liens`, qui garde l'historique |
| P5 Pas de régression silencieuse | ➖ | Moteur non touché |
| P6 Le registre ne quitte pas le worker | ✅ | Table dans `registre.duckdb`, rien dans Postgres |
| P7 Logique métier en Python | ✅ | Tout est dans le paquet ; rien dans `web/` |
| FR-003 Base dans son dernier état valide | ✅ | Remplacement dans une transaction, une ligne `mises_a_jour` par calcul (C3) |

## Critères de succès
- [ ] **C1** : le choix de la mère suit la règle. Tests : ordre des rôles, rôles écartés (commissaires aux comptes, rôle inconnu), parent de plus de 500 enfants, départage par le nombre d'enfants puis par le SIREN, lien fermé ignoré, lien d'une société vers elle-même ignoré
- [ ] **C2** : le sommet et la profondeur suivent la règle. Tests : chaîne de plusieurs niveaux, boucle de deux, boucle de trois avec une société qui y mène, résultat identique quel que soit l'ordre des liens
- [ ] **C3** : la table `arbre` est remplacée dans une transaction. Un échec laisse l'ancienne table et une ligne `echec` dans `mises_a_jour`. Un succès écrit une ligne `succes` (source `arbre`) avec le nombre de sociétés dont le sommet a changé. Aucun nom de personne dans la table, la sortie ni le journal (test)
- [ ] **C4** : le travail de synchro recalcule l'arbre après RNE et SIRENE quand le passage a ajouté ou fermé au moins une ligne. Il ne le recalcule pas sinon. Un échec du calcul fait échouer le travail sans défaire la synchro (tests)
- [ ] **C5** : `mesure_arbre.py` sur `data/registre.duckdb` retrouve la mesure du 2026-10-15 : plus gros arbre ≤ 1 333 sociétés ; VINCI ≥ 281 sociétés de la référence dans l'arbre de VINCI Immobilier Promotion et ≥ 188 dans celui de VINCI Construction ; LVMH ≥ 21 dans celui d'UFIPAR. La durée du calcul sur tout le registre est relevée dans `rapport.md` et tient sous 10 minutes

## Dépendances

**À finir avant** : T007 (registre), T013 (synchro nocturne)
**Suivies de** : le recollage des arbres par les listes publiées (après T043), à écrire avec la mise à jour du PRD
