# T046 — Déposer les documents de périmètre en lot et les retrouver en un seul passage

**Story** : US7 (P1) · **Phase** : 12, carto du pays · **Parallèle** : —
**Couvre** : FR-013 · SC-004 · SC-008 · G6 · R5 · R8 · P3 · P7
**Estimé** : 4 à 6 h

## Contexte
La carto du pays recolle les arbres du registre grâce aux listes publiées par les groupes. Loïc cherche lui-même ces documents (décision du 2026-10-16), quelques centaines avant la mise en ligne (SC-008). Il faut pouvoir les déposer d'un coup, et les retrouver dans le registre sans relire les 13 M de noms de SIRENE pour chacun : 26 à 29 s par document lu seul, mesuré le 2026-10-16 (ARCHI, ADR-007). Remplace le champ de réglage prévu par T044.

## Périmètre
- Une commande `python -m cartofr.perimetre.deposer <SIREN de la tête> <fichier>`, ou `--dossier <dossier>` avec un fichier `index.csv` (SIREN de la tête, fichier). Elle copie chaque fichier dans `data/perimetre/`, garde son empreinte et sa date de dépôt dans la table `documents_perimetre` du registre, et affiche, par document, les lignes retrouvées et refusées avec leur raison.
- Un document déposé pour une tête qui en a déjà un le remplace ; l'ancien fichier est gardé (`data/perimetre/ancien/`), jamais effacé.
- La correspondance de T042 accepte plusieurs documents : une seule lecture des noms pour tous, même résultat ligne par ligne que document par document.
- La recherche des marques sort tout de suite quand le groupe n'a aucune marque (aujourd'hui elle lit tous les noms quand même).

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/perimetre/deposer.py` (nouveau) : la commande
- `worker/cartofr/perimetre/correspondance.py` : `correspondre_plusieurs(con, documents)`
- `worker/cartofr/registre/schema.py` : table `documents_perimetre` (tête, fichier, empreinte, déposé le, lignes, retenues, refusées)
- `worker/cartofr/moteur/marques.py` : aucune lecture sans marque
- `worker/tests/perimetre/` : dépôt, remplacement, plusieurs documents
- `rapport.md`

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G6 Aucun nom de personne | ⚠️ | La sortie de la commande ne recopie que la ligne de la société, comme le CSV des refus de T042 (C4) |
| R5 Hébergement UE | ✅ | Documents sur le serveur, en Allemagne |
| R8 Tests | ✅ | Dépôt, remplacement et correspondance groupée testés sur des documents inventés |
| P3 Aucun appel extérieur | ✅ | La commande lit un fichier local ; elle ne télécharge rien |
| P4 Fermer, jamais effacer | ✅ | Un document remplacé est gardé |
| P7 | ✅ | Tout dans `worker/` |

## Critères de succès
- [x] **C1** : `deposer` sur un fichier ou un dossier copie les documents dans `data/perimetre/`, écrit une ligne par document dans `documents_perimetre` et affiche, par document, le nombre de lignes retrouvées et refusées par raison. Un nouveau dépôt pour la même tête remplace le document et garde l'ancien (tests)
- [x] **C2** : `correspondre_plusieurs` rend, pour chaque ligne, le même résultat que `correspondre` sur son document seul (test sur trois documents inventés, homonymes départagés par le registre compris)
- [x] **C3** : sur LVMH, VINCI, Fnac Darty et Edenred ensemble, la correspondance groupée prend moins de 40 s, contre environ 110 s document par document. Mesure relevée dans `rapport.md`. *Tenu le 2026-10-17 sur LVMH et VINCI seuls : 39 s groupés contre 70 s un par un. Fnac Darty et Edenred ne donnent toujours aucune ligne à l'extraction, ils n'ont pas pu servir*
- [x] **C4** : la sortie de la commande ne contient que des lignes de sociétés et des nombres : jamais les lignes d'avant ni un nom de dirigeant (test)
- [x] **C5** : `chercher_candidates` sans aucune marque rend une liste vide sans lire `unites_legales` (test) ; la non-régression avec les réglages de `config/` est inchangée

## Dépendances
**À finir avant** : T042, T043
**Suivies de** : T048
**Fichiers partagés avec** : `perimetre/correspondance.py` (T042), `moteur/marques.py` (T016)
