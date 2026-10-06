# AGENTS.md — cartoFR

Comment on modifie ce projet. Le **quoi** est dans [`CLAUDE.md`](CLAUDE.md),
le **passé** dans [`MEMORY.md`](MEMORY.md). Ici, c'est le **comment**.

Ce fichier s'adresse autant à un agent qu'à un humain.

---

## 1. Tu es autonome, et c'est un contrat

Ce projet tourne en permissions ouvertes : tu modifies les fichiers et tu
lances les commandes **sans demander**. Ce n'est pas un blanc-seing, c'est un
échange — on te retire les interruptions, tu prends la rigueur en face.

Concrètement, trois obligations remplacent les questions qu'on ne te pose plus.

### Tu te relis avant de rendre

Un travail n'est pas fini quand le code est écrit. Il est fini quand :

```
.venv/bin/python engine.py config/<g>.json   ← pour lvmh, vinci, cmaf (tableau Commandes de CLAUDE.md)
.venv/bin/python compare.py <g>              ← scores au moins égaux à ceux de CLAUDE.md
<lint / typecheck / tests unitaires>         ← à ajouter ici quand la tâche de fondation les pose
```

sont **passées et vertes**. Si l'une échoue, tu corriges — tu ne rends pas en
signalant l'échec comme un détail. Si tu ne peux pas la lancer, tu le dis
explicitement au lieu de laisser croire que c'est validé.

Puis relis ton propre diff, avec la question : *qu'est-ce qui casse ailleurs ?*
Ce que tu viens d'écrire compile ; ce que tu as modifié plus haut dans le
fichier, peut-être pas.

### Tu regardes avant de supprimer

Supprimer ne se rattrape pas. Avant tout `rm`, tout écrasement de fichier,
toute suppression de dossier :

1. **Ouvre ce que tu vas supprimer.** Pas le nom — le contenu.
2. **Dis ce qui disparaît**, en une ligne, avant de le faire.
3. **Dans le doute, ne supprime pas.** Renomme en `.old`, ou demande.

Les suppressions massives (`rm -rf`, `git clean -fdx`, `git reset --hard`) sont
**bloquées en dur** par `.claude/settings.json`. Si l'une est refusée, ce n'est
pas un obstacle à contourner : c'est le signal que tu allais faire quelque chose
d'irréversible. Arrête-toi et demande.

Réécrire un fichier en entier est une suppression déguisée. Préfère une
modification ciblée à un `Write` qui écrase 300 lignes pour en changer 3.

### Tu ne touches jamais à `main`

`main` est protégée par `.claude/hooks/git-guardrail.py`, qui inspecte chaque
commande git **avant** exécution.

**Tu ne gères pas les branches à la main.** C'est `apex -b` qui crée la branche,
et `apex -pr` qui ouvre la PR. Si tu te retrouves à taper `git switch -c` toi-même
en dehors d'apex, c'est probablement que tu aurais dû lancer apex.

Et jamais de `git push`, de PR ou de déploiement **sans demande explicite dans
le message courant**. Une autorisation donnée hier ne vaut pas pour aujourd'hui.

---

## 2. Les secrets : lisibles, jamais ressortis

Tu **peux** lire `.env`, `.env.local` et les fichiers de configuration — c'est
souvent nécessaire pour comprendre comment le projet se branche.

Ce que tu ne fais **jamais** :

| ❌ Interdit | ✅ À la place |
|---|---|
| Écrire une clé en dur dans le code | `os.environ["NOM_DE_LA_CLE"]` / `process.env.NOM_DE_LA_CLE` |
| Recopier la valeur d'un secret dans un message, un commit, un log | Nommer la variable, jamais sa valeur |
| Committer un `.env*` | Mettre à jour `.env.example` avec le **nom** seul |
| Coller un token dans un fichier de test ou un fixture | Une valeur factice évidente : `sk-test-FAKE` |

**Tout secret passe par une variable d'environnement.** Sans exception, pas
même « juste pour tester » — un secret écrit en dur pour un test finit dans
l'historique git, et l'historique ne s'oublie pas.

Quand tu ajoutes une variable, fais les deux gestes ensemble : la lire depuis
l'environnement dans le code, **et** ajouter son nom dans `.env.example` avec
un commentaire disant à quoi elle sert.

Si un secret a été committé, il est **fuité**. On le révoque et on le
régénère ; le retirer du fichier ne suffit pas.

---

## 3. Classement des fichiers

La classe détermine le niveau de prudence.

### 🔴 Constitutionnel — on ne modifie pas sans le dire

Ce qui définit le comportement de toutes les sessions. Une erreur se propage
partout.

- `CLAUDE.md`, `AGENTS.md`, `MEMORY.md`
- `.claude/rules/**`, `.claude/settings.json`, `.claude/hooks/**`
- `.claude/agents/**` s'ils existent

→ Annonce la modification et sa raison. Ne la glisse pas dans un diff plus large.

### 🟠 Structural — le cœur du produit

- Le code applicatif, et d'abord `engine.py` (toute règle qui décide)
- `config/*.json` : un réglage faux fait entrer des centaines de fausses sociétés
- Le schéma de base et les migrations
- `PRD.md`, `ARCHI.md`, `specs/**`

→ Passe par apex. Typecheck, lint et tests verts avant de rendre.

### 🟢 Courant — modification directe

- Documentation, commentaires, README
- Scripts de confort, fixtures de test

→ Fais-le, dis-le en une ligne.

---

## 4. Écrire du code ici

- **Écris comme le code autour.** Même densité de commentaires, mêmes noms,
  mêmes tournures. Un fichier ne doit pas trahir qui l'a écrit.
- **Pas de dépendance nouvelle sans le dire.** Une ligne dans `requirements.txt` ou `package.json`
  engage le projet pour des années. Dis pourquoi, et ce que ça remplace.
- **Le périmètre demandé est le livrable.** Ni plus, ni moins. Si tu vois un
  autre problème en passant, signale-le — ne le corrige pas dans le même diff.
- **Pas d'ID inventé.** Un identifiant fabriqué (ticket, utilisateur, compte)
  passe la relecture sans alerter, puis échoue plus loin — ou réussit sur la
  mauvaise cible. Dans le doute : laisser vide et demander.

---

## 5. Après une tâche significative

Deux gestes, à ne pas oublier :

1. **Coche la tâche** dans `specs/README.md` — mais seulement si **chacun** de
   ses critères de succès est réellement vérifiable dans le code. Une case
   cochée par optimisme rend l'index faux, et un index faux éteint la vigilance
   de tout le monde. Dans le doute, laisse décoché et dis ce qui manque :
   `/apex-converge` le rattrapera, mais il vaut mieux qu'il n'ait rien à
   rattraper.
2. **Écris dans [`MEMORY.md`](MEMORY.md)** si tu as pris une décision non
   évidente, ou payé un piège. La règle du tri : *est-ce que ça sera encore
   vrai la semaine prochaine, et est-ce que quelqu'un d'autre en aurait
   besoin ?* Si oui, ça s'écrit. Sinon, non.

---

## 6. Checklist avant de rendre

- [ ] Typecheck, lint, tests, build : lancés et verts
- [ ] Diff relu, avec la question « qu'est-ce que ça casse ailleurs ? »
- [ ] Aucun secret en dur, aucune valeur de secret recopiée
- [ ] Rien de supprimé sans l'avoir ouvert et annoncé
- [ ] Toujours pas sur `main`, rien de poussé sans demande explicite
- [ ] `MEMORY.md` mis à jour si une décision mérite de survivre
