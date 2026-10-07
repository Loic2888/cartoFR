# T023 — Exporter la carto en CSV, sans aucun nom de personne

**Story** : US2 (P1) · **Phase** : US2 · **Parallèle** : [P]
**Couvre** : FR-007 · SC-005 · G6
**Estimé** : 2 h

## Contexte
Le livrable au client. La licence INPI interdit d'y faire figurer un dirigeant personne physique.

## Périmètre
Route d'export CSV et test automatique qui confronte chaque export à la table des dirigeants.

## Mise en œuvre

### Fichiers à créer ou modifier
- `web/app/(app)/groupes/[id]/cartos/[cartoId]/export/route.ts`
- `worker/tests/test_aucune_personne.py` — LVMH, VINCI, CMAF

### Fonctionnement attendu
- Colonnes : SIREN, nom, niveau, maison mère, preuve, confiance, ciblable et raison, opposition, non-diffusion, date des données
- Encodage UTF-8 avec BOM, séparateur `;` (Excel en français)

### Technologies
- Route Handler Next.js

### Motifs d'architecture
—

## Critères de succès
- [ ] **C1** : `test_aucune_personne.py` ne trouve aucun nom de `dirigeants_personnes` dans les cartos des trois groupes
- [x] **C2** : Le CSV contient une colonne de date des données
- [x] **C3** : Le CSV contient les colonnes `opposition_prospection` et `non_diffusible`

## Tests et validation

### Vérification manuelle
1. Exporter LVMH et l'ouvrir dans Excel

### Cas limites
- Société opposée ou non diffusible : présente et marquée

## Dépendances

**À finir avant** : T021
**Bloque** : T024
**Fichiers partagés avec** : aucun

## Documentation
- **PRD** : FR-007, SC-005
- **ARCHI** : Contrôle constitutionnel G6
