# T038 — Recentrer la proposition IA sur les marques et mesurer son coût

**Story** : US3 (P2) · **Phase** : US3 · **Parallèle** : —
**Couvre** : FR-008 · R4 · P1
**Estimé** : 1 h

## Contexte
Discussion avec Loïc du 2026-10-09, après T037. L'IA ne rend aucune liste de filiales : le moteur les trouve au registre. Lire un rapport annuel en entier ne sert donc pas, et coûte. Ce qui manque au moteur, ce sont les noms de marques et de maisons, donnés par des pages courtes du site. Loïc n'utilisera pas Sonnet.

## Périmètre
Consigne de l'IA recentrée sur les pages de marques et de maisons ; aucun modèle par défaut ; relevé du coût de chaque proposition. Pas de plafond de taille de page (décision de Loïc).

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/ia/proposition.py` — consigne, modèle obligatoire, `Consommation`
- `worker/tests/ia/test_proposition.py` — consigne, consommation additionnée et journalisée
- `.env.example`, `ARCHI.md`, `rapport.md`

### Fonctionnement attendu
- La consigne dit de ne pas chercher la liste des filiales ni l'annexe des comptes consolidés, de viser les pages « nos marques », « nos maisons », « nos métiers », et de n'ouvrir le rapport annuel que si le site ne donne pas ces listes
- Pas de modèle par défaut (décision de Loïc) : sans `CARTOFR_MODELE_IA`, le travail échoue avec un message clair
- Chaque proposition journalise modèle, requêtes, jetons en entrée et en sortie, recherches web et coût en dollars (champ `usage` d'OpenRouter), même quand elle échoue ; des nombres seulement

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| R4 RGPD, journaux | ✅ | Le journal ne porte que des nombres et le nom du modèle (test) |
| G6 Aucun nom de personne | ✅ | Requête inchangée hors consigne ; le test sur les dirigeants passe |
| P1 L'IA ne décide pas | ✅ | Inchangé |

## Critères de succès
- [x] **C1** : la consigne vise les pages de marques et écarte la liste des filiales (test)
- [x] **C2** : sans `CARTOFR_MODELE_IA`, aucun appel n'est fait et le travail échoue (`ModeleIaManquant`, test)
- [x] **C3** : la consommation est additionnée sur les requêtes et journalisée, y compris en échec, sans texte de l'IA (test)
- [ ] **C4** : essai comparatif de quelques modèles (Haiku, Mistral, DeepSeek…) sur LVMH, VINCI et CMAF : corrections par rapport à `config/` et coût réel, puis choix du modèle par Loïc — demande une clé OpenRouter

## Dépendances

**À finir avant** : T037
**Bloque** : la mesure SC-007 de T026
**Fichiers partagés avec** : `worker/cartofr/ia/proposition.py` (T025, T037)
