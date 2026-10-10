# T039 — Améliorer le rappel de la proposition IA

**Story** : US3 (P2) · **Phase** : US3 · **Parallèle** : —
**Couvre** : FR-008 · SC-007 · R4 · P1 · P2
**Estimé** : 2 h

## Contexte
Premier essai réel (2026-10-10, Claude Haiku 5.5 par OpenRouter) : presque aucune marque fausse, mais un rappel faible. L'IA retrouvait 23 des 74 marques de `config/lvmh.json`, 18 sur 71 pour VINCI, 18 sur 52 pour CMAF. Elle n'utilisait que 3 à 6 de ses 16 recherches et lectures. Décision de Loïc : améliorer le rappel.

## Périmètre
Consigne d'exhaustivité, contexte élargi à tout le groupe, budget d'outils plus large, limite de sortie relevée. Plus deux défauts trouvés en mesurant : le compteur de recherches web et le message d'une réponse coupée.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/ia/proposition.py`
- `worker/tests/ia/test_proposition.py`
- `docs/registre-traitements.md` — ce qui part vers l'IA : 150 sociétés du groupe au plus
- `rapport.md` — la mesure avant et après

### Fonctionnement attendu
- Consigne : être exhaustif sur ce que les sources citent, sans rien inventer ; parcourir chaque pôle d'activité du site ; utiliser les noms des sociétés du groupe comme pistes ; rapport annuel jamais en entier
- Contexte : la tête et les 150 plus grosses sociétés du groupe au registre (liens directs ou non, en vigueur), au lieu des seules filiales directes
- Outils : 10 recherches et 20 lectures au plus, 30 appels au total (plafond d'OpenRouter)
- Sortie : 64 000 jetons au plus ; une réponse coupée par la limite est « tronquée », vérifié avant de lire l'appel d'outil
- Le compteur de recherches lit `server_tool_use_details`, le champ réel d'OpenRouter

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G6 Aucun nom de personne | ✅ | Le contexte élargi reste fait de sociétés (`societes`, personnes morales) ; le test sur les dirigeants passe |
| R4 RGPD | ✅ | Registre des traitements mis à jour (150 sociétés au plus) |
| R5 Hébergement UE | ✅ | Condition inchangée : données de sociétés, routage ZDR |
| P1, P2 L'IA ne décide pas, l'humain valide | ✅ | Plus d'éléments proposés, tous à relire ; la règle des homonymes range toujours les marques |

## Critères de succès
- [x] **C1** : la mesure sur LVMH, VINCI et CMAF montre un rappel en hausse sur les trois groupes (`rapport.md`)
- [x] **C2** : une proposition exhaustive n'est plus coupée (CMAF passe) ; une réponse coupée est signalée « tronquée » (test)
- [x] **C3** : le compteur de recherches web lit le champ d'OpenRouter (test)
- [x] **C4** : le contexte prend les sous-filiales, sans la tête ni les liens fermés, les plus grosses d'abord (test)

## Dépendances

**À finir avant** : T037, T038
**Fichiers partagés avec** : `worker/cartofr/ia/proposition.py` (T025, T037, T038)
