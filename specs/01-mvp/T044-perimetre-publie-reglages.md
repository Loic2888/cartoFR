# T044 — Mettre le périmètre publié dans les réglages du groupe, et le faire trouver par l'IA

**Story** : US2 et US3 · **Phase** : 10, périmètre publié · **Parallèle** : —
**Couvre** : FR-005 · FR-008 · SC-007 · R1 · R2 · R3 · R5 · P1 · P2 · P3 · P7
**Estimé** : 5 à 7 h

## Contexte
Avec T042 et T043, une carto se construit à partir d'un document : la liste des sociétés consolidées du groupe. Il faut que le consultant puisse le donner, et que l'IA le trouve. Le 2026-10-14, l'IA de recherche a trouvé seule la liste de VINCI, alors qu'on ne la lui demandait pas. Mais le site de la BFCM (CMAF) refuse tout téléchargement automatique (403) : le dépôt d'un PDF par le consultant est indispensable.

## Périmètre
- Réglages : un champ « périmètre publié » (URL, ou PDF déposé), versionné et validé comme le reste des réglages (principe 2). Le worker télécharge l'URL au moment de la validation, jamais pendant une carto (principe 3), et garde le document.
- Proposition IA : elle cherche d'abord l'URL du périmètre de consolidation (document d'enregistrement universel, liste publiée), avec sa source. Les marques passent au second plan.
- Écran : le consultant voit combien de lignes ont été retrouvées, les refus de T042 (introuvables, homonymes) et peut les reprendre à la main.
- PRD : SC-007 est réécrit pour mesurer la carto obtenue sans correction (sociétés retrouvées, « en plus » expliqués), et non plus le nombre de corrections. Texte proposé à Loïc, il décide.

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| R1 Français | ✅ | Libellés, erreurs de téléchargement traduites (« Le site du groupe refuse le téléchargement : déposez le PDF ») |
| R2, R3 | ✅ | Champ de dépôt avec label, au clavier, vérifié à 320 px |
| R5 Hébergement UE | ⚠️ | Les documents déposés restent sur le serveur, en UE (T005) |
| P1 L'IA ne décide pas | ✅ | L'IA propose une URL ; le consultant la valide ; les règles de T042 et T043 décident |
| P2 Réglages validés | ✅ | Le document est un réglage, validé comme les autres |
| P3 Aucun appel extérieur pendant une carto | ✅ | Téléchargement à la validation, document stocké |
| P7 Logique en Python | ✅ | Extraction et correspondance dans le worker ; le web affiche |

## Critères de succès
- [ ] **C1** : un consultant donne une URL ou dépose un PDF. Le worker le garde et la carto suivante l'utilise sans réseau
- [ ] **C2** : un téléchargement refusé (403, page HTML au lieu d'un PDF) donne un message français qui propose le dépôt
- [ ] **C3** : la proposition IA rend l'URL du périmètre pour VINCI et LVMH, avec sa source. Coût par proposition relevé
- [ ] **C4** : SC-007 réécrit dans `PRD.md`, une fois la décision de Loïc prise

## Dépendances

**À finir avant** : T042, T043
**Fichiers partagés avec** : écran des réglages (T020, T026), `worker/cartofr/ia/proposition.py` (T025, T037 à T040)
