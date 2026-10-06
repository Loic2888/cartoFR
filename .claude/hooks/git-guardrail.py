#!/usr/bin/env python3
"""Garde-fou git — hook PreToolUse (Bash) pour Claude Code.

Bloque, avant execution, dans toute session Claude Code de ce projet :
  1. tout push (direct, forced, delete, mirror) vers une branche protegee ;
  2. tout commit dont le sujet n'est pas au format Conventional Commits.

Ce n'est pas une consigne qu'on peut oublier au bout de 40 messages : le hook
refuse la commande. Le harnais l'execute, pas le modele.

Sortie : exit 2 = commande bloquee (stderr renvoye a Claude) ; exit 0 = autorisee.

Installation : voir ../README.md
Verification : python3 .claude/hooks/git-guardrail.py --selftest
"""
from __future__ import annotations  # "str | None" sur python3 < 3.10

import json
import re
import shlex
import subprocess
import sys

# ============================================================
# CONFIG — les seules lignes a editer
# ============================================================

# Branches sur lesquelles on ne pousse jamais directement.
PROTECTED = {"main", "master"}

# Promotions autorisees, sous la forme (source, destination).
# Exemple d'un projet ou la prod est un fast-forward de main :
#   PROTECTED  = {"main", "master", "production"}
#   PROMOTIONS = {("main", "production")}
# Laisser vide si tu n'as pas de branche de deploiement.
PROMOTIONS: set[tuple[str, str]] = set()

# Verifier le format des messages de commit.
ENFORCE_CONVENTIONAL_COMMITS = True

# Format de branche attendu, affiche dans le message de blocage.
BRANCH_HINT = "<user>/<id-ticket>-<slug>"

# ============================================================

TYPES = "feat|fix|docs|style|refactor|perf|test|chore|build|ci|revert"
SEMANTIC = re.compile(rf"^({TYPES})(\([^)]+\))?!?: .+")
# Messages generes par git lui-meme, ou destines a etre absorbes par un squash.
EXEMPT_SUBJECT = re.compile(r"^(Merge |Revert |fixup!|squash!)")

# Options de `git push` qui consomment l'argument suivant.
PUSH_OPTS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")


def segments(cmd: str) -> list[list[str]]:
    """Decoupe une ligne shell en commandes, chacune tokenisee.

    shlex nous protege des faux positifs : dans `echo "git push origin main"`,
    la chaine citee reste UN token, donc "push" n'apparait pas comme mot.
    """
    out = []
    for raw in SEGMENT_SPLIT.split(cmd):
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(shlex.split(raw))
        except ValueError:  # guillemet non ferme, heredoc… : on garde le brut
            out.append(raw.split())
    return out


def norm(ref: str) -> str:
    """Normalise une ref en nom de branche court."""
    ref = ref.lstrip("+")
    for prefix in ("refs/heads/", "heads/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def push_targets(tokens: list[str], branch: str) -> tuple[list[tuple[str, str]], bool]:
    """Retourne les couples (source, destination) d'un `git push`, et si tout est pousse.

    Un push sans refspec pousse la branche courante vers son homonyme distant.
    """
    i = tokens.index("push") + 1
    positional, delete, everything = [], False, False

    while i < len(tokens):
        tok = tokens[i]
        if tok in ("--delete", "-d"):
            delete = True
        elif tok in ("--all", "--mirror"):
            everything = True
        elif tok in PUSH_OPTS_WITH_VALUE:
            i += 1  # l'option consomme l'argument suivant
        elif not tok.startswith("-"):
            positional.append(tok)
        i += 1

    # Le premier positionnel est le remote (origin, une URL…), le reste des refspecs.
    refspecs = positional[1:] if len(positional) > 1 else []

    if everything:
        return [], True
    if not refspecs:
        return ([(branch, branch)] if branch else []), False
    if delete:
        return [("", norm(r)) for r in refspecs], False

    pairs = []
    for spec in refspecs:
        spec = spec.lstrip("+")
        if ":" in spec:
            src, dst = spec.split(":", 1)
        else:
            src = dst = spec
        src = norm(src)
        pairs.append((branch if src in ("HEAD", "") else src, norm(dst)))
    return pairs, False


def commit_subject(tokens: list[str], raw: str) -> str | None:
    """Extrait le sujet d'un `git commit`, ou None si non verifiable."""
    value = None
    for i, tok in enumerate(tokens):
        if tok in ("-m", "--message") and i + 1 < len(tokens):
            value = tokens[i + 1]
            break
        if tok.startswith("--message="):
            value = tok[len("--message="):]
            break
        if tok.startswith("-m") and len(tok) > 2:
            value = tok[2:]
            break

    # Heredoc (`-m "$(cat <<'EOF' …)"`) : le sujet est la ligne suivant le marqueur.
    if "<<" in raw:
        m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?\r?\n(.*)", raw, re.S)
        if not m:
            return None
        body = m.group(2)
        for line in body.splitlines():
            if line.strip():
                return line.strip()
        return None

    if value is None or value.startswith("$("):
        return None  # rien a verifier, ou valeur calculee a l'execution
    return (value.splitlines() or [""])[0].strip()


def block_push(dst: str) -> str:
    return (
        f"BLOQUE — push direct sur `{dst}` interdit.\n"
        f"Convention : 1 ticket = 1 branche = 1 PR.\n"
        f"  git switch -c {BRANCH_HINT}\n"
        f"  git push -u origin {BRANCH_HINT}\n"
        f"puis ouvre une PR vers `{dst}`.\n"
        f"Ref : CLAUDE.md, section Garde-fous."
    )


def verdict(cmd: str, branch: str) -> str | None:
    """Message de blocage, ou None si la commande passe."""
    for tokens in segments(cmd):
        if "git" not in tokens:
            continue

        if "push" in tokens:
            pairs, everything = push_targets(tokens, branch)
            if everything and PROTECTED:
                return (
                    "BLOQUE — `git push --all` / `--mirror` pousse aussi les "
                    f"branches protegees ({', '.join(sorted(PROTECTED))}).\n"
                    "Pousse la branche courante nommement."
                )
            for src, dst in pairs:
                if dst in PROTECTED and (src, dst) not in PROMOTIONS:
                    return block_push(dst)

        if ENFORCE_CONVENTIONAL_COMMITS and "commit" in tokens:
            subject = commit_subject(tokens, cmd)
            if subject and not EXEMPT_SUBJECT.match(subject) and not SEMANTIC.match(subject):
                return (
                    "BLOQUE — message de commit non conforme (Conventional Commits).\n"
                    f'Recu   : "{subject}"\n'
                    f"Attendu : type(scope): sujet — type dans "
                    f"{TYPES.replace('|', ' | ')}\n"
                    "Sujet a l'imperatif, minuscule, sans point final.\n"
                    "Ex : feat(auth): ajoute le refresh de token\n"
                    "Ref : .claude/rules/git-pr.md"
                )
    return None


def current_branch() -> str:
    try:
        return subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return ""


def selftest() -> None:
    cases = [
        # (commande, branche courante, doit bloquer ?)
        ("git push origin main", "loic/42-x", True),
        ("git push -u origin main", "loic/42-x", True),
        ("git push", "main", True),
        ("git push origin HEAD:main", "loic/42-x", True),
        ("git push origin refs/heads/main", "loic/42-x", True),
        ("git push --force origin main", "loic/42-x", True),
        ("git push origin --delete main", "loic/42-x", True),
        ("git push --all origin", "loic/42-x", True),
        ("git push origin master", "loic/42-x", True),
        # branche qui contient le mot "main" mais n'est pas main
        ("git push -u origin loic/42-fix-main-menu", "loic/42-fix-main-menu", False),
        ("git push -u origin loic/42-x", "loic/42-x", False),
        ("git push", "loic/42-x", False),
        ("git push --force-with-lease", "loic/42-x", False),
        ("git -C /tmp/repo push origin main", "loic/42-x", True),
        # une commande citee n'est pas une commande executee
        ('echo "git push origin main"', "loic/42-x", False),
        ("git push origin loic/42-x && git status", "loic/42-x", False),
        ("git status && git push origin main", "loic/42-x", True),
        # commits
        ('git commit -m "fix: corrige le calcul de TVA"', "loic/42-x", False),
        ('git commit -m "feat(auth): ajoute le refresh"', "loic/42-x", False),
        ('git commit -m "feat!: retire l endpoint v1"', "loic/42-x", False),
        ('git commit -m "corrige le calcul"', "loic/42-x", True),
        ('git commit -m "WIP"', "loic/42-x", True),
        ('git commit -m "Merge branch main"', "loic/42-x", False),
        ("git commit --amend --no-edit", "loic/42-x", False),
        ("git commit -m \"$(printf 'x')\"", "loic/42-x", False),
        # heredoc : sujet lu apres le marqueur
        ('git commit -m "$(cat <<\'EOF\'\nfix: corrige X\n\nCo-Authored-By: Y\nEOF\n)"', "loic/42-x", False),
        ('git commit -m "$(cat <<\'EOF\'\ncorrige X\nEOF\n)"', "loic/42-x", True),
        # non-git
        ("ls -la", "main", False),
        ("npm run build", "main", False),
    ]
    failed = 0
    for cmd, branch, expected in cases:
        got = verdict(cmd, branch) is not None
        if got != expected:
            failed += 1
            print(f"FAIL {cmd!r} sur {branch!r} : bloque={got}, attendu={expected}")
    if failed:
        sys.exit(f"{failed}/{len(cases)} cas en echec")
    print(f"OK — {len(cases)} cas")


def main() -> None:
    if "--selftest" in sys.argv:
        selftest()
        return

    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # entree illisible : ne jamais bloquer sur un doute technique

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    msg = verdict(cmd, current_branch())
    if msg:
        print(msg, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
