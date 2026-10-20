# T051 — Corriger la carto d'un groupe sans étape de validation, et en montrer l'effet

**Story** : US8 (P2) · **Phase** : 12, carto du pays · **Parallèle** : —
**Couvre** : FR-005 · R1 · R2 · R3 · R7 · R8 · P2 · P7
**Estimé** : 4 à 6 h

## Contexte
Principe 2 amendé le 2026-10-16 : une carto existe sans validation humaine ; une correction est versionnée, datée, et son effet est affiché. Aujourd'hui, le worker refuse une carto dont les réglages ne sont pas validés (`verifier_reglages`, T021), et l'écran demande une validation (T020).

## Périmètre
- Une version de `reglages` enregistrée s'applique au calcul suivant, sans `valide_le`. La colonne reste (historique), elle n'est plus exigée.
- La carto corrigée d'une organisation part de la carto du pays : tête du groupe et document du groupe, plus les corrections. Elle garde son effet : sociétés ajoutées et retirées par rapport à la carto du pays. *(2026-10-19 : l'effet se mesure contre la carto sans correction, voir C2.)*
- L'écran de réglages devient « Corrections » : plus de bouton « Valider », un bouton « Enregistrer et recalculer ». La page de la carto corrigée montre l'effet.
- La proposition de l'IA (US3, P3) reste une proposition, enregistrée seulement quand le consultant l'enregistre.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/jobs/carto.py` : plus de refus sans `valide_le` ; carte de départ = carto du pays ; effet
- `supabase/migrations/` : colonnes de l'effet dans `cartos`
- `web/app/(app)/groupes/[id]/reglages/`, `.../cartos/[cartoId]/` : libellés, effet
- tests worker (`worker/tests/jobs/`) et web

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| P2 amendé | ✅ | Plus de validation ; auteur, date et effet gardés (C1, C2) |
| R7 Isolation | ✅ | Corrections et cartos corrigées sous RLS ; test « A ne voit pas les corrections de B » (C4) |
| R8 Tests | ✅ | Calcul de l'effet testé |
| R1, R2, R3 | ✅ | Libellés français, écran en une colonne à 320 px, au clavier |

## Critères de succès
- [x] **C1** : une version de corrections enregistrée sans `valide_le` est appliquée par le travail `carto` (test) ; l'auteur et la date restent enregistrés
- [x] **C2** : la carto corrigée enregistre le nombre de sociétés ajoutées et retirées par rapport au groupe dans `pays.duckdb`, et la page l'affiche (tests) — *réécrit le 2026-10-19 (décision de Loïc) : l'effet compte ce que les corrections changent, contre la carto sans correction (même tête, même document), pas contre `pays.duckdb`, dont l'écart mêle la méthode (arbre du registre, départage). Voir `rapport.md`.*
- [x] **C3** : sur LVMH, les réglages de `config/lvmh.json` appliqués comme corrections donnent au moins 155/172 (PRD US8 ; 166/172 le 2026-10-16 avec le document) — *168/172 le 2026-10-19, `worker/scripts/mesure_corrections.py`*
- [x] **C4** : un membre de l'organisation A ne voit ni les corrections ni les cartos corrigées de B (test RLS)
- [x] **C5** : aucun libellé « valider » ne reste dans l'écran des corrections ; tout est en français

## Dépendances
**À finir avant** : T050
**Fichiers partagés avec** : `jobs/carto.py` (T021, T027), écran des réglages (T020, T026)
