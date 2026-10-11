# T040 — Signaler à la revue les marques qu'aucune société ne porte

**Story** : US3 (P2) · **Phase** : US3 · **Parallèle** : —
**Couvre** : FR-008 · SC-007 · R1 · R3 · P1 · P2 · P7
**Estimé** : 1 h

## Contexte
Après T039 (2026-10-10), la proposition IA contient du bruit : des marques sans activité en France (domaines viticoles étrangers dans LVMH). Deux pistes essayées et écartées le 2026-10-11 (mesures dans `rapport.md`) : une consigne « seulement les marques actives en France » fait baisser le rappel ; des passes par pôle d'activité coûtent 2 à 4 fois plus sans gain net. Écarter d'office les marques qu'aucune société du registre ne porte ferait perdre de vraies marques : 6 marques validées sur 75 dans LVMH (Veuve Clicquot, Moët & Chandon : leur société s'appelle MHCS), 6 sur 71 dans VINCI, 4 sur 53 dans CMAF. Décision de Loïc : signaler, ne rien écarter.

## Périmètre
Le worker compte, pour chaque marque proposée, les sociétés actives qui la portent dans et hors du groupe. Une marque qu'aucune ne porte est marquée `sans_societe` ; l'écran de revue l'affiche « À vérifier », en texte. Rien n'est écarté, le rangement ne change pas.

## Mise en œuvre

### Fichiers à créer ou modifier
- `worker/cartofr/ia/proposition.py` — `Porteurs`, `compter_porteurs`, `sans_societe`, champ `ElementRange.sans_societe`, `ranger`
- `worker/cartofr/jobs/proposition.py` — signalement et compte dans le journal
- `worker/tests/ia/test_proposition.py`
- `web/lib/reglages/proposition.ts`, `web/app/(app)/groupes/[id]/reglages/proposition.tsx`, `web/lib/reglages/proposition.test.ts`
- `rapport.md`

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| R1 Français | ✅ | Mention « À vérifier : aucune société du registre ne porte ce nom… » |
| R3 Accessibilité | ✅ | Le signalement est un texte, pas une couleur |
| P1, P2 | ✅ | Règle écrite dans le worker ; le consultant décide, rien n'est écarté |
| P7 Pas de règle du moteur dans `web/` | ✅ | Le worker décide `sans_societe` ; le web l'affiche |
| G6 Aucun nom de personne | ✅ | Seuls des comptes de sociétés sont ajoutés |

## Critères de succès
- [x] **C1** : une marque qu'aucune société active ne porte, ni dans le groupe ni dehors, est signalée et gardée ; les autres ne le sont pas (tests worker, de bout en bout en base)
- [x] **C2** : l'écran de revue lit le signalement et l'affiche en texte (test web)
- [x] **C3** : vérifié sur les réglages validés : un filtre aurait écarté 6, 6 et 4 vraies marques ; le signalement n'en écarte aucune

## Dépendances

**À finir avant** : T039
**Fichiers partagés avec** : `worker/cartofr/ia/proposition.py` (T025, T037 à T039), écran de revue (T026)
