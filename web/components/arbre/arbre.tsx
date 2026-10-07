"use client";

// L'arbre d'un groupe (T022, FR-007), au motif WAI-ARIA treeview
// (https://www.w3.org/WAI/ARIA/apg/patterns/treeview/).
//
// Clavier, sur une société (treeitem) :
// - Flèche bas / haut : société visible suivante / précédente ;
// - Flèche droite : déplie ; si c'est déjà déplié, va à la première filiale ;
// - Flèche gauche : replie ; si c'est déjà replié, remonte à la maison mère ;
// - Entrée ou Espace : déplie ou replie ;
// - Début / Fin : première / dernière société visible ;
// - Tab : la preuve de la société (voir preuve.tsx), puis la sortie de l'arbre.
// Un seul élément de l'arbre est dans l'ordre de tabulation (tabIndex
// itinérant) : celui qui a eu le focus en dernier.
//
// Au départ, seul le premier niveau est déplié. Affichage seulement : l'arbre
// est déjà décidé par le worker (principe 7).
import { type FocusEvent, type KeyboardEvent, type MouseEvent, useCallback, useId, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { type Noeud as NoeudArbre, parents, visibles } from "@/lib/cartos/arbre";

import { Noeud, idDom } from "./noeud";

type Props = {
  racines: NoeudArbre[];
  /** Nom accessible de l'arbre, par exemple « Arbre du groupe LVMH ». */
  libelle: string;
};

/** Pour chaque nœud, ses ancêtres et son parent. */
function genealogie(racines: readonly NoeudArbre[]) {
  const ancetres = new Map<string, ReadonlySet<string>>();
  const parent = new Map<string, string | null>();
  const pile: { noeud: NoeudArbre; chemin: ReadonlySet<string>; parent: string | null }[] = racines.map(
    (noeud) => ({ noeud, chemin: new Set<string>(), parent: null }),
  );
  while (pile.length > 0) {
    const { noeud, chemin, parent: p } = pile.pop()!;
    ancetres.set(noeud.id, chemin);
    parent.set(noeud.id, p);
    const suite = new Set(chemin).add(noeud.id);
    for (const e of noeud.enfants) pile.push({ noeud: e, chemin: suite, parent: noeud.id });
  }
  return { ancetres, parent };
}

export function Arbre({ racines, libelle }: Props) {
  const prefixe = `arbre${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const { ancetres, parent } = useMemo(() => genealogie(racines), [racines]);
  const [ouverts, setOuverts] = useState<ReadonlySet<string>>(
    () => new Set(racines.filter((r) => r.enfants.length > 0).map((r) => r.id)),
  );
  const [choisi, setChoisi] = useState<string | null>(racines[0]?.id ?? null);
  const liste = useMemo(() => visibles(racines, ouverts), [racines, ouverts]);
  const montres = useMemo(() => new Set(liste.map((v) => v.noeud.id)), [liste]);

  // L'élément actif doit être visible : si un ancêtre a été replié, c'est le
  // plus proche ancêtre visible qui prend le relais (l'arbre garde sa place
  // dans l'ordre de tabulation).
  const actif = useMemo(() => {
    if (choisi === null) return racines[0]?.id ?? "";
    let id: string | null = choisi;
    while (id !== null && !montres.has(id)) id = parent.get(id) ?? null;
    return id ?? racines[0]?.id ?? "";
  }, [choisi, montres, parent, racines]);

  const focaliser = useCallback(
    (id: string) => {
      setChoisi(id);
      document.getElementById(idDom(prefixe, id))?.focus();
    },
    [prefixe],
  );

  const basculer = useCallback((id: string, ouvrir?: boolean) => {
    setOuverts((avant) => {
      const deja = avant.has(id);
      const voulu = ouvrir ?? !deja;
      if (voulu === deja) return avant;
      const apres = new Set(avant);
      if (voulu) apres.add(id);
      else apres.delete(id);
      return apres;
    });
  }, []);

  function auClavier(e: KeyboardEvent<HTMLUListElement>) {
    const cible = e.target as HTMLElement;
    // Seules les touches reçues par une société : pas celles de sa preuve.
    if (cible.getAttribute("role") !== "treeitem" || e.altKey || e.ctrlKey || e.metaKey) return;
    const id = cible.dataset.noeud;
    const i = liste.findIndex((v) => v.noeud.id === id);
    if (id === undefined || i < 0) return;
    const { noeud } = liste[i];
    const aDesEnfants = noeud.enfants.length > 0;
    const ouvert = ouverts.has(id);

    switch (e.key) {
      case "ArrowDown":
        if (i + 1 < liste.length) focaliser(liste[i + 1].noeud.id);
        break;
      case "ArrowUp":
        if (i > 0) focaliser(liste[i - 1].noeud.id);
        break;
      case "ArrowRight":
        if (aDesEnfants && !ouvert) basculer(id, true);
        else if (aDesEnfants) focaliser(noeud.enfants[0].id);
        break;
      case "ArrowLeft": {
        const p = liste[i].parent;
        if (aDesEnfants && ouvert) basculer(id, false);
        else if (p !== null) focaliser(p);
        break;
      }
      case "Enter":
      case " ":
        if (aDesEnfants) basculer(id);
        break;
      case "Home":
        focaliser(liste[0].noeud.id);
        break;
      case "End":
        focaliser(liste[liste.length - 1].noeud.id);
        break;
      default:
        return;
    }
    e.preventDefault();
    e.stopPropagation();
  }

  function auClic(e: MouseEvent<HTMLUListElement>) {
    const bascule = (e.target as HTMLElement).closest<HTMLElement>("[data-bascule]");
    const id = bascule?.dataset.bascule;
    if (id === undefined) return;
    basculer(id);
    focaliser(id);
  }

  function auFocus(e: FocusEvent<HTMLUListElement>) {
    const id = (e.target as HTMLElement).dataset.noeud;
    if (e.target.getAttribute("role") === "treeitem" && id !== undefined) setChoisi(id);
  }

  const toutDeplier = () => setOuverts(new Set(parents(racines)));
  const toutReplier = () => setOuverts(new Set());

  if (racines.length === 0) {
    return <p className="text-sm text-muted-foreground">Aucune société dans cette carto.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button type="button" variant="outline" onClick={toutDeplier} className="w-full sm:w-auto">
          Tout déplier
        </Button>
        <Button type="button" variant="outline" onClick={toutReplier} className="w-full sm:w-auto">
          Tout replier
        </Button>
      </div>
      <p id={`${prefixe}-aide`} className="text-sm text-muted-foreground">
        Au clavier : flèches haut et bas pour passer d&apos;une société à l&apos;autre, droite et gauche
        pour déplier ou replier, Entrée pour déplier, Tab pour la preuve de la société.
      </p>
      <ul
        role="tree"
        aria-label={libelle}
        aria-describedby={`${prefixe}-aide`}
        onKeyDown={auClavier}
        onClick={auClic}
        onFocus={auFocus}
        className="flex min-w-0 flex-col"
      >
        {racines.map((r, i) => (
          <Noeud
            key={r.id}
            noeud={r}
            niveau={1}
            position={i + 1}
            taille={racines.length}
            ouverts={ouverts}
            actif={actif}
            prefixe={prefixe}
            ancetres={ancetres}
          />
        ))}
      </ul>
    </div>
  );
}
