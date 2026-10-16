# T047 — Ranger une société réclamée par deux groupes dans un seul

**Story** : US7 (P1) · **Phase** : 12, carto du pays · **Parallèle** : [P] avec T046
**Couvre** : FR-012 · SC-001 · R8 · P1 · P7
**Estimé** : 3 à 5 h

## Contexte
Dans la carto du pays, chaque société active appartient à exactement une carto (FR-012). Deux groupes peuvent réclamer la même société : deux documents l'inscrivent, ou la descente du registre depuis un groupe atteint une société qu'un autre document inscrit. Cas typique : les groupes imbriqués, quand la tête d'un groupe est inscrite dans le document d'un autre (ARCHI, travail `pays`, étape 6).

## Périmètre
Une fonction pure, sans registre : elle reçoit les réclamations (groupe, société, manière : inscription en intégration globale, descente par le registre, arbre non réclamé), et rend pour chaque société un seul groupe, avec la raison du choix. Règle proposée, à confirmer avec Loïc pendant le plan d'`apex` :
1. un groupe dont la tête est inscrite en intégration globale dans le document d'un autre est rangé sous celui-ci, avec toutes ses sociétés (groupes imbriqués) ;
2. sinon, l'inscription directe dans un document passe avant la descente par le registre ;
3. entre deux inscriptions, le taux d'intérêt le plus haut ; à taux égal, le groupe le plus grand, puis la plus petite tête par SIREN ;
4. entre deux descentes, le groupe dont la société est la plus proche de la tête (niveau le plus bas), puis la plus petite tête ;
5. un arbre qu'aucun groupe ne réclame reste son propre groupe.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/pays/__init__.py`, `worker/cartofr/pays/departage.py` (nouveaux)
- `worker/tests/pays/test_departage.py` : réclamations inventées

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| R8 Tests | ✅ | Chaque étape de la règle a son test, cas limites compris (C1, C2) |
| P1 L'IA ne décide pas | ✅ | Règle écrite, sans IA |
| P7 | ✅ | Paquet Python |

## Critères de succès
- [ ] **C1** : chaque étape de la règle est testée seule : groupes imbriqués (y compris sur trois niveaux, et une boucle A inscrit B, B inscrit A, départagée par la plus petite tête), inscription contre descente, taux, taille, niveau, SIREN
- [ ] **C2** : le résultat ne dépend pas de l'ordre des réclamations (test sur des permutations), et chaque société en entrée sort une fois et une seule
- [ ] **C3** : chaque société rangée porte la raison du choix quand il y a eu départage (« inscrite au document de … », « groupe imbriqué sous … »), sans nom de personne

## Dépendances
**À finir avant** : —
**Suivies de** : T048
