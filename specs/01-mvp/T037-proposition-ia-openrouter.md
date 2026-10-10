# T037 — Faire passer la proposition IA par OpenRouter

**Story** : US3 (P2) · **Phase** : US3 · **Parallèle** : —
**Couvre** : FR-008 · R4 · R5 · G5 · G6 · P1
**Estimé** : 2 h

## Contexte
Décision de Loïc du 2026-10-09 : l'IA passe par OpenRouter au lieu de l'API Anthropic en direct (T025). Un seul compte et une seule facture, et le modèle se change sans toucher au code.

## Périmètre
Remplacer l'appel à l'API Anthropic du travail `proposition` par un appel à OpenRouter, sans changer ce que reçoit la revue (T026) : mêmes éléments, mêmes sources, même règle des homonymes, mêmes éléments déjà validés gardés.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/ia/proposition.py` — requête au format Chat Completions, client HTTP OpenRouter
- `worker/cartofr/jobs/proposition.py` — docstring (variables d'environnement)
- `worker/tests/ia/test_proposition.py` — réponses OpenRouter simulées, client HTTP simulé
- `worker/pyproject.toml` — retirer `anthropic` ; `httpx` suffit
- `.env.example` — `OPENROUTER_API_KEY` (nom seul) à la place de `ANTHROPIC_API_KEY`
- `ARCHI.md` — section IA, condition R5, coûts
- `docs/registre-traitements.md` — traitement 5 : OpenRouter en sous-traitant
- `rapport.md` — la décision

### Fonctionnement attendu
- `POST https://openrouter.ai/api/v1/chat/completions`, clé dans l'en-tête `Authorization` seulement
- Modèle `anthropic/claude-sonnet-5.5` par défaut, `CARTOFR_MODELE_IA` pour en changer
- Recherche et lecture web par les outils serveur `openrouter:web_search` et `openrouter:web_fetch`, exécutés par OpenRouter ; la proposition arrive par un appel de fonction à schéma strict
- `provider: {zdr: true, data_collection: "deny"}` sur chaque requête
- Erreur HTTP, refus, réponse tronquée ou illisible : `PropositionImpossible` avec un message français sûr ; le journal ne garde que le statut HTTP

### Technologies
- httpx, pytest

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G5 Secrets | ✅ | Clé lue dans l'environnement, nom seul dans `.env.example`, jamais journalisée (test) |
| G6 Aucun nom de personne | ✅ | Même requête que T025 : le test qui confronte tout l'envoi aux dirigeants passe |
| R4 RGPD | ⚠️ | Sous-traitant ajouté au registre des traitements ; conservation chez OpenRouter à décider (registre, point 10) |
| R5 Hébergement UE | ⚠️ | OpenRouter et le fournisseur du modèle sont aux États-Unis : seules des données de sociétés partent, routage limité au ZDR. Condition écrite dans `ARCHI.md` |
| P1 L'IA ne décide pas | ✅ | Inchangé : version non validée, la base refuse de la valider |
| P3 Aucun appel extérieur pendant une carto | ➖ | La proposition n'est pas une carto |

## Critères de succès
- [x] **C1** : plus aucun appel à l'API Anthropic en direct ; `anthropic` retiré des dépendances du worker
- [x] **C2** : la requête envoyée porte les outils serveur OpenRouter, la fonction de proposition stricte et `provider` ZDR (test)
- [x] **C3** : le test « aucun nom de dirigeant dans la requête » passe sur le nouveau format
- [x] **C4** : erreurs HTTP 401, 402, 429, 5xx, réseau et réponse illisible donnent un message français, sans clé ni corps de réponse dans le journal (test)
- [x] **C5** : une proposition réelle sur un groupe connu, comparée à `config/` — fait le 2026-10-10 sur LVMH, VINCI et CMAF (`rapport.md`, T039)

## Tests et validation

### Vérification manuelle
1. Avec `OPENROUTER_API_KEY` dans `.env`, lancer une proposition sur LVMH depuis l'écran des réglages ; comparer à `config/lvmh.json` ; noter le coût affiché par OpenRouter.

### Cas limites
- Le modèle appelle un autre outil que la proposition : ignoré
- Arguments de la fonction qui ne sont pas un objet JSON : `PropositionImpossible`

## Dépendances

**À finir avant** : T025, T026
**Bloque** : la mesure SC-007 de T026 (C3)
**Fichiers partagés avec** : `worker/cartofr/ia/proposition.py` (T025)

## Documentation
- **PRD** : FR-008, US3
- **ARCHI** : IA (P2, US3), R5
