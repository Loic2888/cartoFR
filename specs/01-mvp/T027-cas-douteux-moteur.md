# T027 — Sortir les cas douteux et réutiliser les décisions

**Story** : US4 (P2) · **Phase** : US4 · **Parallèle** : séquentiel
**Couvre** : FR-009
**Estimé** : 3 h

## Contexte
Les cas douteux sont aujourd'hui noyés dans l'arbre en confiance C.

## Périmètre
Le moteur range chaque cas douteux avec ses indices et la règle qui l'a placé là. Les décisions du consultant sont reprises à la carto suivante.

## Mise en œuvre

### Fichiers à créer ou modifier
- `supabase/migrations/0003_cas_douteux.sql` — `carto_cas`, `decisions`, RLS
- `worker/cartofr/moteur/moteur.py` — sortie des cas
- `worker/cartofr/jobs/carto.py` — lecture des décisions
- `worker/tests/moteur/test_cas_douteux.py`

### Fonctionnement attendu
- Cas : confiance C, co-entreprise, participation sans contrôle, société étrangère

### Technologies
- DuckDB, psycopg

### Motifs d'architecture
La décision humaine s'applique, la règle reste écrite.

## Critères de succès
- [x] **C1** : `test_cas_douteux.py` vérifie que chaque cas porte sa règle et ses indices
- [x] **C2** : `test_cas_douteux.py` vérifie qu'une décision « écarter » est reprise à la carto suivante
- [x] **C3** : `0003_cas_douteux.sql` active RLS sur `carto_cas` et `decisions`
- [x] **C4** : La non-régression reste aux scores de T016

## Tests et validation

### Vérification manuelle
1. Relancer VINCI et compter les cas

### Cas limites
- Aucun propre à cette tâche dans la spec. Traités et testés (2026-10-08) : décision sur une société disparue ou sans indice (sans objet), décision contradictoire plus récente, décision sur la tête (ignorée), entité extérieure absente de SIRENE (jamais désignée).

### Résultat (2026-10-08)
- Cas douteux : LVMH 80, VINCI 569, CMAF 353. Non-régression inchangée, cartos identiques champ par champ. Détail dans `rapport.md`.

## Dépendances

**À finir avant** : T021
**Bloque** : T028
**Fichiers partagés avec** : `worker/cartofr/moteur/moteur.py` (T016), `worker/cartofr/jobs/carto.py` (T021)

## Documentation
- **PRD** : FR-009
- **ARCHI** : —
