# T050 — Lire la carto d'une société, sans attendre de calcul

**Story** : US2 (P1) · **Phase** : 12, carto du pays · **Parallèle** : —
**Couvre** : FR-004 · FR-007 · SC-002 · SC-005 · G6 · R1 · R2 · R3 · R7 · P6 · P7
**Estimé** : 5 à 7 h

## Contexte
US2 réécrite le 2026-10-16 : le consultant cherche une société et lit l'arbre de son groupe, déjà calculé dans `pays.duckdb` (ARCHI, ADR-006). *Précisé le 2026-10-18 (Loïc) : la carto d'une société est elle et ce qui descend d'elle, jamais les autres filiales de sa mère ou de ses actionnaires ; sa mère est nommée au-dessus, avec un lien.* Aujourd'hui, l'app demande de choisir une tête, d'écrire des réglages, puis de lancer une carto.

## Périmètre
- Une route interne `GET /groupe?siren=` dans le service de recherche : la société en tête et tout ce qui descend d'elle, sous-groupes compris ; sa mère directe (SIREN, nom, sans ses autres filiales) ; la tête de son groupe ou de son groupe parent si ce n'est pas elle ; sa date des données. Chercher la tête d'un groupe rend donc le groupe entier. L'arbre porte les sociétés, maisons mères, preuves, confiance, ciblable, opposition et non-diffusion. La route lit `pays.duckdb` en lecture seule.
- La recherche (`/recherche`) rend, pour chaque société trouvée, son groupe et la taille de ce groupe.
- Une page `/pays/[siren]` : si la société a une mère, la page la nomme en tête avec un lien vers sa carto ; si elle appartient à un groupe plus grand (LVMH sous Christian Dior), un lien « Voir le groupe Christian Dior en entier » ; une mère entrepreneur individuel est dite « personne physique, non affichée », sans lien ; puis l'arbre, avec le composant d'arbre existant (T022), la date des données, et la mention « calculée sans correction » ou « corrigée » (si l'organisation a une carto corrigée, lien vers elle).
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
- [x] **C1** : `/groupe?siren=` rend la société et tout ce qui descend d'elle, sans aucune de ses sœurs ni des autres filiales de ses actionnaires, avec sa mère directe ; pour une société absente de `pays_societes`, elle seule ; 404 en français pour un SIREN inconnu ; 503 si `pays.duckdb` n'existe pas encore (tests)
- [ ] **C2** *(route mesurée le 2026-10-19 : VINCI en 0,15 à 0,34 s ; affichage de la page non mesuré, pile Supabase non lancée)* : sur le registre réel, la route rend la carto de VINCI en moins d'1 s, et la page s'affiche en moins de 10 s après la recherche (SC-002), mesuré et relevé dans `rapport.md`
- [x] **C3** : aucun nom de personne ni SIREN d'entrepreneur individuel dans la réponse de la route ni dans le CSV, y compris quand la mère est un entrepreneur individuel (test)
- [ ] **C4** *(non vérifié à la main le 2026-10-19)* : la page fonctionne au clavier et à 320 px ; la date des données et « calculée sans correction » sont visibles
- [x] **C6** : la page d'un groupe emboîté dit de quel groupe il est la filiale et ouvre la carto de ce groupe entier, sous-groupes compris (tests de la route et de la page)
- [x] **C5** : le CSV exporté depuis la page a les mêmes colonnes que celui de T023 et la date des données

## Dépendances
**À finir avant** : T048
**Suivies de** : T051
**Fichiers partagés avec** : `api_recherche.py` (T019, T029, T041)
