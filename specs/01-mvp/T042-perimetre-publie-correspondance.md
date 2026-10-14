# T042 — Lire le périmètre publié d'un groupe et retrouver ses sociétés dans le registre

**Story** : US2 (P1) · **Phase** : 10, périmètre publié · **Parallèle** : —
**Couvre** : FR-006 · SC-001 · SC-007 · G6 · R6 · R8 · P1 · P3 · P5 · P6 · P7
**Estimé** : 4 à 6 h

## Contexte
Mesures du 2026-10-14 (`rapport.md`). Sans réglages faits à la main, le moteur retrouve 2/172 sociétés de LVMH et 3/1 007 de VINCI. La proposition IA brute en retrouve 15 % et 3 %. Le registre dit qui dirige, pas qui possède : le groupe y est coupé en blocs que rien ne recolle. Les groupes cotés publient la liste de leurs sociétés consolidées. Croisée avec SIRENE puis complétée par les blocs du registre, elle donne 75 % de VINCI et 75 % de LVMH, sans IA ni réglage humain. Décision de Loïc : le but est une carto complète produite seule.

## Périmètre
Le worker lit un document de périmètre (PDF ou page HTML, déjà téléchargé ou déposé) et en tire les sociétés situées en France, outre-mer compris. Il les retrouve dans le registre par une règle écrite et rend, pour chaque ligne, un SIREN retenu ou la raison du refus (introuvable, homonymes). Il ne touche pas au moteur : c'est T043. Il n'appelle aucun réseau : le téléchargement est T044.

Règle de correspondance, mesurée le 2026-10-14 :
- nom normalisé (accents, casse, ponctuation, formes juridiques, abréviations « Ste », « Cie »…) identique à la dénomination SIRENE d'une seule société active (personne morale) ;
- sinon, plusieurs porteurs : départagés par la commune du siège quand le document la donne, ou par le registre (un seul porteur déjà relié au groupe) ;
- sinon : non retenu, rendu « homonymes » avec leur nombre.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/perimetre/__init__.py`, `extraction.py` (lignes du document → nom, ville, pays, méthode, taux), `correspondance.py` (nom → SIREN)
- `worker/tests/perimetre/` : fixtures **générées** au format des listes VINCI et LVMH, aucun document réel copié
- `worker/scripts/mesure_perimetre.py` : rejoue la mesure du 2026-10-14 depuis un document local (les documents restent hors git, dans `out/`)
- `rapport.md`

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G6 Aucun nom de personne | ✅ | Le document liste des sociétés. Une dénomination qui contient un nom reste une donnée de société (décision T023). `dirigeants_personnes` n'est pas lu par la correspondance |
| G5, G6 Licence, données | ⚠️ | Les documents des groupes ne vont jamais dans git (`out/`) ; les tests utilisent des fixtures générées |
| R6 Aucune donnée client en dev | ✅ | Documents publics des groupes, pas des cartos client |
| R8 Tests sur la logique métier | ✅ | Extraction et correspondance arrivent avec leurs tests, cas limites compris (C1, C2) |
| P1 L'IA ne décide pas | ✅ | Aucune IA dans cette tâche : règle écrite et reproductible |
| P3 Aucun appel extérieur pendant une carto | ✅ | Le worker lit un document déjà stocké |
| P5 Pas de régression silencieuse | ➖ | Moteur non touché (T043) |
| P6, P7 | ✅ | Tout est dans le paquet Python ; rien dans `web/` |

## Critères de succès
- [ ] **C1** : l'extraction lit les deux formats mesurés : VINCI (« nom pays taux méthode ») et LVMH (« nom ville, pays méthode taux % », noms sur deux lignes, en-têtes et numéros de page ignorés). Elle ne garde que la France et l'outre-mer (tests sur fixtures générées)
- [ ] **C2** : la correspondance rend un SIREN pour un porteur unique et départage par la commune ou par le registre ; elle refuse et explique dans les autres cas. Tests : homonymes, abréviations, forme juridique en tête ou en fin, société fermée, entrepreneur individuel écarté
- [ ] **C3** : `mesure_perimetre.py` sur les documents du 2026-10-14 retrouve au moins les chiffres de la mesure jetable : VINCI 844 noms à un seul porteur ou plus, LVMH 176 retenus ou plus
- [ ] **C4** : la liste des lignes refusées (introuvables, homonymes) sort avec la raison, pour qu'un humain ou T044 puisse les reprendre

## Dépendances

**À finir avant** : —
**Suivies de** : T043 (entrée dans le moteur), T044 (document dans les réglages, dans l'app)
