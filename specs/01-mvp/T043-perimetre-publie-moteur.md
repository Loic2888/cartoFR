# T043 — Faire entrer dans la carto les sociétés du périmètre publié et leurs blocs

**Story** : US2 (P1) · **Phase** : 10, périmètre publié · **Parallèle** : —
**Couvre** : FR-006 · SC-001 · R8 · P1 · P2 · P4 · P5 · P7
**Estimé** : 4 à 6 h

## Contexte
T042 rend les SIREN d'un périmètre publié. Mesure du 2026-10-14 : la liste seule donne 35 % de VINCI et 59 % de LVMH ; en descendant dans les blocs du registre sous chaque société retenue, on monte à 75 % pour les deux. Sur VINCI, 89 % des sociétés de la liste absentes de la référence sont reliées au groupe par le registre. Ce sont donc surtout des oublis de la référence Basile.

## Périmètre
Un nouvel indice du moteur, « périmètre publié » : une société retenue par T042 entre dans le groupe avec sa preuve (document, ligne, taux d'intérêt). Le moteur descend ensuite les liens de société depuis elle, avec les règles existantes. Les règles par marques restent et s'ajoutent.

Tranché avec Loïc le 2026-10-16 :
- confiance d'une entrée par le périmètre : A si un mandat au registre la rattache au groupe, B sinon ;
- une société mise en équivalence (pas contrôlée) n'entre pas, même présidée par le groupe : le document l'emporte. Elle est rangée en participation sans contrôle, et le consultant peut la retenir.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/moteur/moteur.py`, `modele.py` : indice `perimetre`, raison d'entrée, preuve
- `worker/tests/moteur/` : règles et cas limites
- `worker/scripts/non_regression.py` : mode « sans marques + périmètre » à côté du mode actuel
- `rapport.md`

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| R8 Tests sur la logique métier | ✅ | L'indice et la confiance arrivent avec leurs tests |
| P1 L'IA ne décide pas | ✅ | L'entrée vient d'une règle sur un document publié par le groupe |
| P2 Réglages validés par un humain | ✅ | Le document de périmètre fait partie des réglages validés (T044) |
| P4 Fermer, jamais effacer | ➖ | Le registre n'est pas modifié |
| P5 Pas de régression silencieuse | ⚠️ | Non-régression sur LVMH, VINCI et CMAF dans les deux modes, avant la PR (C3) |
| P7 Logique en Python | ✅ | Tout est dans `worker/` |

## Critères de succès
- [x] **C1** : une société du périmètre entre avec l'indice « périmètre publié » et sa preuve. Ses filiales du registre entrent par les règles existantes. Aucun nom de personne dans la preuve
- [x] **C2** : une société mise en équivalence n'entre pas comme filiale contrôlée
- [x] **C3** : avec les réglages validés plus le périmètre, les scores ne baissent pas : LVMH ≥ 154/172, VINCI ≥ 813/1 007, CMAF ≥ 43/52. Les « en plus » nouveaux sont comptés et expliqués. *Tenu le 2026-10-16 : LVMH 166, VINCI 861, CMAF 43 (sans document)*
- [x] **C4** : sans aucune marque, périmètre seul, LVMH et VINCI ≥ 75 % chacun. C'est la carto produite sans travail humain. *Tenu le 2026-10-16 : tête seule, sans aucun autre réglage (décision de Loïc), LVMH 142/172 (83 %), VINCI 836/1 007 (83 %)*
- [x] **C5** : `rapport.md` donne les scores, la part des « en plus » reliés au groupe par le registre, et la durée

## Dépendances

**À finir avant** : T042
**Fichiers partagés avec** : `worker/cartofr/moteur/moteur.py` (T016, T027, T033 à T036)
