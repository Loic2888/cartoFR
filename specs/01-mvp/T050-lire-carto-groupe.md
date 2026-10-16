# T050 — Lire la carto du groupe d'une société, sans attendre de calcul

**Story** : US2 (P1) · **Phase** : 12, carto du pays · **Parallèle** : —
**Couvre** : FR-004 · FR-007 · SC-002 · SC-005 · G6 · R1 · R2 · R3 · R7 · P6 · P7
**Estimé** : 5 à 7 h

## Contexte
US2 réécrite le 2026-10-16 : le consultant cherche une société et lit l'arbre de son groupe, déjà calculé dans `pays.duckdb` (ARCHI, ADR-006). Aujourd'hui, l'app demande de choisir une tête, d'écrire des réglages, puis de lancer une carto.

## Périmètre
- Une route interne `GET /groupe?siren=` dans le service de recherche : le groupe de la société, sa tête, sa date des données, et l'arbre (sociétés, maisons mères, preuves, confiance, ciblable, opposition, non-diffusion). Elle lit `pays.duckdb` en lecture seule.
- La recherche (`/recherche`) rend, pour chaque société trouvée, son groupe et la taille de ce groupe.
- Une page `/pays/[siren de la tête]` : l'arbre, avec le composant d'arbre existant (T022), la date des données, et la mention « calculée sans correction » ou « corrigée » (si l'organisation a une carto corrigée, lien vers elle).
- L'export CSV (T023) depuis cette page.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/api_recherche.py` : route `/groupe`, groupe dans `/recherche`
- `worker/tests/test_api_recherche.py`
- `web/app/(app)/pays/[siren]/page.tsx` (nouveau), recherche de l'accueil et de `groupes/nouveau`
- `web/lib/` : client de la route `/groupe`, export CSV
- tests web (vitest)

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G6, SC-005 | ⚠️ | La route ne rend aucune personne : test sur un groupe dont le sommet est un entrepreneur individuel (C3) |
| R1 Français | ✅ | Libellés, états vides et erreurs en français (« La carto du pays n'est pas encore calculée ») |
| R2 Responsive | ⚠️ | Vérification à 320 px (C4) |
| R3 Accessibilité | ✅ | Arbre `treeview` existant ; « corrigée / calculée sans correction » écrit en toutes lettres |
| R7 Isolation | ✅ | La carto du pays est commune ; le lien vers une carto corrigée ne montre que celles de l'organisation (RLS existante) |
| P6, P7 | ✅ | Lecture dans le worker ; Next.js affiche |

## Critères de succès
- [ ] **C1** : `/groupe?siren=` rend le groupe d'une société de `pays_societes`, et pour une société absente, un groupe d'une seule société ; 404 en français pour un SIREN inconnu ; 503 si `pays.duckdb` n'existe pas encore (tests)
- [ ] **C2** : sur le registre réel, la route rend le groupe de VINCI en moins d'1 s, et la page s'affiche en moins de 10 s après la recherche (SC-002), mesuré et relevé dans `rapport.md`
- [ ] **C3** : aucun nom de personne ni SIREN d'entrepreneur individuel dans la réponse de la route ni dans le CSV (test)
- [ ] **C4** : la page fonctionne au clavier et à 320 px ; la date des données et « calculée sans correction » sont visibles
- [ ] **C5** : le CSV exporté depuis la page a les mêmes colonnes que celui de T023 et la date des données

## Dépendances
**À finir avant** : T048
**Suivies de** : T051
**Fichiers partagés avec** : `api_recherche.py` (T019, T029, T041)
