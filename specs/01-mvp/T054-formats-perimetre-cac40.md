# T054 — Lire les listes du CAC 40 et noter la mère des groupes étrangers

**Story** : US7 (P1) · **Phase** : 12, carto du pays · **Parallèle** : —
**Couvre** : FR-013 · SC-008 · R8 · P1 · P3 · P5 · G6
**Estimé** : 1 jour

## Contexte
Le 2026-10-20, Loïc a trouvé les listes de sociétés consolidées de 40 groupes du CAC 40 et de 6 groupes cotés à Paris dont la mère est à l'étranger (`out/perimetre/cac40/listes/inventaire.csv`). L'extraction (formats VINCI, LVMH, ESEF de CMAF) n'en lisait aucune : pays en titre de section, colonnes dans un autre ordre, rangées HTML coupées par l'indentation. Et `texte_document` refusait un paquet ESEF de plus de 50 Mo (Accor, Saint-Gobain…), alors que la limite prévue est de 300 Mo.

Décision de Loïc du 2026-10-21 : pour un groupe dont la mère est à l'étranger, on choisit une tête en France, et on indique qui est la mère et d'où elle vient.

## Périmètre
- Nouveaux formats, essayés seulement si les anciens ne lisent rien : un document déjà lu l'est toujours de la même façon.
- Limite de 300 Mo pour un paquet ESEF ou une page HTML ; 50 Mo pour le reste.
- La mère étrangère (raison sociale, code pays ISO) se déclare au dépôt, ou dans `index.csv`. Elle est gardée dans `documents_perimetre` et `pays_groupes`, puis affichée dans l'en-tête de la carto. Elle ne décide rien dans la carto.
- Dépôt des listes lisibles dans `data/registre.duckdb`.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/perimetre/extraction.py` : formats T054, rangées HTML, limite de taille
- `worker/cartofr/perimetre/pays.py` (nouveau) : noms de pays et de zones en titre de section
- `worker/cartofr/perimetre/deposer.py`, `worker/cartofr/registre/schema.py`, `worker/cartofr/registre/construire.py` : mère étrangère
- `worker/cartofr/pays/calcul.py`, `pays/schema.py`, `pays/lecture.py` : mère étrangère dans la carto du pays
- `web/lib/pays.ts`, `web/app/(app)/pays/[siren]/en-tete.tsx` : affichage
- `worker/tests/perimetre/test_formats_t054.py` (nouveau), `test_deposer.py`, `worker/tests/pays/test_calcul.py`, `en-tete.test.tsx`
- `rapport.md`

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G6 Aucun nom de personne | ✅ | La preuve est la rangée la plus courte qui porte le nom, jamais une ligne d'avant de trop (test) ; la mère est une raison sociale de société |
| G6 Rien de `data/` ni `out/` dans git | ✅ | Documents, extrait de CASA et `index.csv` restent dans `out/` et `data/` |
| P1 L'IA ne décide pas | ✅ | Tête et mère saisies dans l'index, sourcées (GLEIF, registre), pas calculées par IA |
| P3 Aucun appel extérieur | ✅ | La recherche web a servi à remplir l'index, pas au calcul |
| P4 Fermer, jamais effacer | ✅ | Un nouveau dépôt (même une mère changée) ferme l'ancien |
| P5 Pas de régression silencieuse | ✅ | Formats T054 en dernier recours ; LVMH, VINCI, CMAF lus à l'identique ; non-régression inchangée |
| R1 Français | ✅ | Messages et libellé « Mère du groupe, hors de France » |
| R8 Tests | ✅ | Un test par format, par règle de rejet, par règle de dépôt |

## Critères de succès
- [x] **C1** : Engie, Crédit Agricole S.A., TotalEnergies, Société Générale, BNP Paribas et Carrefour donnent des lignes, au nombre de sociétés en France que leur document annonce (tests sur des lignes inventées de chaque forme)
- [x] **C2** : un paquet ESEF de plus de 50 Mo est lu jusqu'à 300 Mo, un PDF de plus de 50 Mo reste refusé (tests)
- [x] **C3** : LVMH, VINCI et CMAF, déjà déposés, se lisent ligne pour ligne à l'identique ; la non-régression ne bouge pas
- [x] **C4** : Airbus, Eurofins, Euronext, Stellantis et STMicroelectronics sont déposés sur une tête en France, avec leur mère et son pays ; la mère se lit dans `pays_groupes` et dans l'en-tête de la carto (tests)
- [x] **C5** : les listes lisibles sont déposées dans `data/registre.duckdb`, avec leurs lignes retrouvées et refusées dans `rapport.md`

## Dépendances
**À finir avant** : T046, T049
**Suivies de** : T048 (recalcul de la carto du pays avec ces documents)
**Fichiers partagés avec** : `perimetre/extraction.py` (T042, T049, T053), `perimetre/deposer.py` (T046)
