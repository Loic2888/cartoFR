// La preuve d'un lien (T022, FR-007), dépliable. Texte écrit par le worker,
// sans nom de personne (garde-fou 6), rendu comme du texte : jamais du HTML.
//
// Au clavier, dans l'arbre : seul le résumé de la société active est dans
// l'ordre de tabulation (tabIndex 0), comme la société elle-même. Tab depuis
// la société mène à « Preuve », Entrée ou Espace l'ouvre (comportement natif
// de <details>), Échap ou Maj+Tab ramène sur la société. Les flèches ne
// jouent pas ici : l'arbre n'écoute que les touches reçues par un treeitem.
import type { KeyboardEvent } from "react";

type Props = {
  texte: string | null;
  /** La société est l'élément actif de l'arbre : son résumé est atteignable par Tab. */
  focusable: boolean;
};

function revenirALaSociete(e: KeyboardEvent<HTMLElement>) {
  if (e.key !== "Escape") return;
  const societe = e.currentTarget.closest<HTMLElement>('[role="treeitem"]');
  if (!societe) return;
  e.preventDefault();
  e.stopPropagation();
  societe.focus();
}

export function Preuve({ texte, focusable }: Props) {
  return (
    <details className="group/preuve text-sm">
      <summary
        tabIndex={focusable ? 0 : -1}
        onKeyDown={revenirALaSociete}
        className="inline-flex min-h-11 cursor-pointer items-center gap-1 rounded-md px-1 font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring md:min-h-8"
      >
        <span className="group-open/preuve:hidden">Voir la preuve</span>
        <span className="hidden group-open/preuve:inline">Masquer la preuve</span>
      </summary>
      <p className="mt-1 rounded-md border bg-muted/40 px-3 py-2 break-words whitespace-pre-line">
        {texte?.trim() ? texte : "Aucune preuve écrite pour cette société."}
      </p>
    </details>
  );
}
