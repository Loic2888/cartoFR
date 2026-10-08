# Tâches d'implémentation — cartoFR

Date : 2026-10-06. Sources : `PRD.md`, `ARCHI.md`.

## Le projet en bref

**D'après le PRD** : une app interne Youno qui tient sa propre copie du registre français, mise à jour avec au plus 7 jours de retard (US1). Elle rend en quelques minutes l'arbre d'un groupe, avec la preuve, la confiance A/B/C et l'indication ciblable de chaque lien (US2).
**Stack (ARCHI)** : Next.js 16 + shadcn/ui · Supabase auto-hébergé (Postgres, Auth, RLS) · worker Python 3.12 + DuckDB · VPS Hetzner CX43 en UE, Docker Compose.
**État actuel** :
- ✅ Prototype à la racine : moteur (`engine.py`), tables nationales (`data/rne_links/`, 1,6 M liens), non-régression (`compare.py`). Scores au 2026-10-06 : LVMH 90 %, VINCI 81 %, CMAF 83 %.
- ✅ `worker/` (T001) et `web/` (T002) : squelettes, lint, typecheck et tests en place (commandes dans `AGENTS.md`).
- ✅ `infra/` (T004) : Docker Compose, Supabase réduit, Caddy, testé en local. CI GitHub Actions sur chaque PR (T003).
- ✅ Schéma de base et RLS (T006), `data/registre.duckdb` (T007), client de l'API diff INPI et mesure du quota (T010).
- ❌ Pas encore de serveur (T005).

## Comment lire ce fichier

- `[P]` : la tâche peut tourner en même temps que les autres `[P]` de la même phase dont elle ne dépend pas. Elles ne partagent aucun fichier.
- Les phases s'enchaînent dans l'ordre. Dans une phase, on suit aussi les dépendances (« À finir avant »).
- **MVP = Setup + Foundational + US1 + US2.** Le PRD a deux stories P1, et les deux sont nécessaires. Tout ce qui suit s'ajoute au MVP.
- La série `T9NN` est réservée à `/apex-converge`.

## Phase 1 : Setup

- [x] `T001` [P] — Poser le paquet Python du worker et son outillage
- [x] `T002` [P] — Poser l'application Next.js et son outillage
- [x] `T003` [P] — Brancher la CI sur chaque PR *(après T001, T002)*
- [x] `T004` [P] — Écrire l'infrastructure Docker Compose *(après T001, T002)*
- [ ] `T005` — Déployer sur le VPS Hetzner et poser les sauvegardes *(préalable humain : compte Hetzner et nom de domaine)*

## Phase 2 : Foundational (bloque toutes les stories)

- [x] `T006` [P] — Créer le schéma de base et le cloisonnement RLS
- [x] `T007` [P] — Construire `registre.duckdb` avec dates de début et de fin
- [x] `T008` — Écrire la file de travaux du worker *(après T006)*
- [x] `T009` [P] — Mettre en place la connexion par lien magique et le gabarit *(après T006)*

## Phase 3 : US1 — La base se met à jour toute seule (P1) 🎯 MVP

- [x] `T010` [P] — Mesurer le quota réel de l'API diff de l'INPI *(peut commencer dès T001)*
- [x] `T011` [P] — Appliquer les changements du RNE au registre *(après T010)*
- [x] `T012` [P] — Appliquer les changements de SIRENE au registre
- [x] `T013` — Planifier la synchro nocturne et publier l'état du registre
- [x] `T014` — Afficher l'état du registre aux admins
- [ ] `T015` — Rattraper le registre et contrôler la fraîcheur

**Point de contrôle** : le registre se met à jour seul chaque nuit. Un admin voit dans l'app la date des données et tout échec, avec sa cause. Le contrôle de fraîcheur trouve 10 changements sur 10 publiés dans les 7 derniers jours.

## Phase 4 : US2 — Cartographier un groupe (P1) 🎯 MVP

- [x] `T016` [P] — Ranger le moteur dans le paquet et le brancher sur `registre.duckdb` *(peut commencer dès T007)*
- [x] `T017` — Tester chaque règle qui décide *(après T016)*
- [x] `T018` [P] — Créer les tables des groupes, réglages et cartos
- [x] `T019` [P] — Chercher et choisir la tête d'un groupe
- [x] `T020` [P] — Saisir, versionner et valider les réglages
- [x] `T021` — Lancer une carto et enregistrer le résultat
- [x] `T022` [P] — Afficher l'arbre du groupe avec ses preuves
- [x] `T023` [P] — Exporter la carto en CSV, sans aucun nom de personne
- [ ] `T024` — Faire la recette du MVP

**Point de contrôle** : un consultant se connecte, cherche « LVMH », valide ses réglages, lance la carto, parcourt l'arbre au clavier et sur mobile, puis exporte un CSV sans aucun nom de personne. Le tout en moins de 30 minutes, avec au moins les scores du prototype.

## Phase 5 : US3 — L'IA propose les réglages (P2)

- [ ] `T025` — Faire proposer les réglages par l'IA
- [ ] `T026` — Afficher la proposition et mesurer les corrections

## Phase 6 : US4 — Traiter les cas douteux (P2)

- [ ] `T027` — Sortir les cas douteux et réutiliser les décisions
- [ ] `T028` — Lister les cas douteux et décider

## Phase 7 : US5 — Export HubSpot et Cargo (P3)

- [ ] `T029` [P] — Exporter les 6 tables du skill account-mapping

## Phase 8 : US6 — Site web et page LinkedIn (P3)

- [ ] `T030` [P] — Ajouter le domaine et la page LinkedIn des sociétés *(`needs-spec` : source à choisir)*

## Phase 8b : Moteur — défauts trouvés par T017 (P1, jamais en parallèle : même fichier)

- [x] `T033` — Faire entrer une marque sûre même avec un mandat « Autre »
- [x] `T034` — Exclure les comités même avec un nom accentué
- [ ] `T035` — Atteindre le point fixe au-delà de 8 niveaux, ou le signaler
- [ ] `T036` — Garder un niveau cohérent avec la maison mère après une boucle coupée

## Phase 9 : Finitions

- [ ] `T031` [P] — Écrire le registre des traitements et permettre la suppression d'un compte
- [ ] `T032` — Retirer les scripts du prototype une fois la parité atteinte

## Carte des dépendances

```
T001 ─┬─ T003
T002 ─┼─ T004 ── T005 ─────────────────────────────── T015
      │    └──── T006 ─┬─ T008 ─┬─ T013 ── T014        │
      │                │        │    └──────── T015 ───┤
      │                ├─ T009 ─┼─ T014                │
      │                │        ├─ T019 ─┐             │
      │                │        └─ T020 ─┤             │
      │                └─ T018 ─┬────────┤             │
T001 ── T007 ─┬─ T011 (+T010) ─ T013     │             │
              ├─ T012 ──────── T013      │             │
              └─ T016 ─┬─ T017           │             │
                       └──────────── T021 ─┬─ T022 ─┬─ T024 ── T032
                                           └─ T023 ─┘
T021 ─┬─ T025 ── T026        T021 ── T027 ── T028
      └─ T029 (+T019)        T013 ── T030        T009 ── T031
```

## Tâches parallèles

Vérifié par fichiers partagés : deux tâches `[P]` d'une même phase ne touchent aucun fichier commun.

- **Setup** : T001 ∥ T002, puis T003 ∥ T004.
- **Foundational** : T006 ∥ T007, puis T008 ∥ T009 (T009 touche `infra/docker-compose.yml`, qu'aucune autre tâche de la phase ne modifie).
- **US1** : T011 ∥ T012 (`synchro_rne.py` et `synchro_sirene.py`, tests séparés).
- **US2** : T016 ∥ T018, puis T019 ∥ T020, puis T022 ∥ T023.
- **Jamais en parallèle**, parce qu'elles partagent des fichiers :
  - `worker/cartofr/jobs/__init__.py` : T008, T013, T021, T025 ;
  - `worker/tests/test_rls.py` : T006, T018 ;
  - `infra/docker-compose.yml` : T004, T009, T019 ;
  - `worker/cartofr/moteur/moteur.py` : T016, T027 ;
  - `rapport.md` : T010, T015, T024, T026.

## Couverture du PRD

| Story | Priorité | Tâches | Exigences | Critères de succès |
|---|---|---|---|---|
| US1 | P1 | T010–T015 (+ T007) | FR-001, FR-002, FR-003 | SC-003 |
| US2 | P1 | T016–T024 (+ T019 recherche) | FR-004, FR-005, FR-006, FR-007 | SC-001, SC-002, SC-004, SC-005 |
| US3 | P2 | T025, T026 | FR-008 | SC-007 |
| US4 | P2 | T027, T028 | FR-009 | — |
| US5 | P3 | T029 | FR-010 | — |
| US6 | P3 | T030 | FR-011 | — |

| Exigence | Tâches |
|---|---|
| FR-001 | T010, T011, T012, T013 |
| FR-002 | T007, T011 |
| FR-003 | T006, T007, T013, T014 |
| FR-004 | T019 |
| FR-005 | T008, T018, T020, T021 |
| FR-006 | T016, T017, T021 |
| FR-007 | T018, T022, T023 |
| FR-008 | T025, T026 |
| FR-009 | T027, T028 |
| FR-010 | T029 |
| FR-011 | T030 |

| Critère | Tâches |
|---|---|
| SC-001 Justesse | T016 (non-régression du moteur), T024 (depuis l'app) |
| SC-002 Moins de 30 min | T024 |
| SC-003 Fraîcheur ≤ 7 jours | T011, T012, T015 |
| SC-004 Moins de 5 min | T021 (durée enregistrée), T024 |
| SC-005 Aucun nom de personne | T023 |
| SC-006 Adoption à 3 mois | **Aucune tâche** : c'est une mesure faite 3 mois après la livraison du MVP, en comptant les missions. À noter dans `rapport.md` à cette date. |
| SC-007 IA | T026 |

## Contrôle constitutionnel

| Règle | Verdict | Portée par |
|---|---|---|
| G1-G4 Branches, PR, commits, squash | ✅ | Hook `git-guardrail.py` + T003 (CI = condition de merge) |
| G5 Aucun secret dans le code | ✅ | T004 C2 et C3 (`env_file`, `.env.example` sans valeur), T010 (identifiants depuis `.env`) |
| G6 Licence INPI | ✅ | T018 C3 et T006 C3 (aucune colonne de personne), T016 C3, T019 C2, T023 C1, T029 C2 |
| R1 Français | ✅ | T002 C5 (`lang="fr"`), T009 C3 (erreurs traduites), libellés de chaque écran |
| R2 Responsive | ✅ | Vérification à 320 px dans T002, T014, T019, T020, T022, T028, et T024 C4 |
| R3 Accessibilité | ✅ | T022 C1 et C2 (treeview au clavier), T014 C3 et T022 C3 (le sens ne passe pas par la seule couleur), T009 C4 et T020 C3 (labels), T024 C4 |
| R4 RGPD | ✅ | T031 (registre des traitements, suppression, journaux), T004 C4 (rotation), T009 (e-mail seul) |
| R5 Hébergement UE | ✅ | T005 C3 (région UE), T025 C2 (aucune personne envoyée à l'API Claude) |
| R6 Aucune donnée client réelle en dev | ✅ | T011 C5, T012, T017 : fixtures générées. Les références Basile restent dans `basile/`, hors git (T016) |
| R7 Isolation multi-tenant | ✅ | T006 C2, T018 C2 (A ne voit pas B), T021 C2 (`organisation_id` copié) |
| R8 Tests sur la logique métier | ✅ | T017 (règles du moteur), T011 et T012 (synchro), T027 (cas douteux) |
| P1 L'IA ne décide pas | ✅ | T025 C1 (proposition non validée) |
| P2 Réglages validés par un humain | ✅ | T020, T021 C1 (refus d'une version non validée) |
| P3 Aucun appel extérieur pendant une carto | ✅ | T016 C2 (moteur avec le réseau coupé), T030 C1 |
| P4 Fermer, jamais effacer | ✅ | T011 C2 et C4 |
| P5 Pas de régression silencieuse | ✅ | T016 C1, T024 C1, T027 C4, T032 C3. La non-régression a besoin de `data/` (19 Go) : elle tourne en local avant chaque PR qui touche le moteur, pas dans la CI |
| P6 Le registre ne quitte pas le worker | ✅ | T018 C3, T019 C2 et C3 |
| P7 Logique métier en Python | ✅ | T022 (« aucune règle du moteur dans `web/` »), T020 C1 (même schéma des deux côtés) |

Aucun ⛔.

## Temps estimé

- **MVP (T001–T024)** : 48 à 61 h.
- **Total (T001–T032)** : 66 à 81 h.

À temps partiel, le MVP tient dans la fenêtre de 4 à 6 semaines du PRD si l'on y passe 10 à 12 h par semaine.
