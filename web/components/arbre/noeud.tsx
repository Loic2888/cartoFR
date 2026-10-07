// Un nœud de l'arbre (T022) : une société et ses filiales, au motif WAI-ARIA
// treeview. Tout ce qui compte est écrit en texte (C3) : confiance, ciblable,
// opposition à la prospection, non-diffusion. La couleur et l'icône ne font
// qu'accompagner le texte.
//
// Les événements (clic sur le chevron, focus, clavier) sont écoutés une seule
// fois par l'arbre (arbre.tsx) : ce composant ne fait qu'afficher, et ne se
// redessine que si son sous-arbre change (memo), pour tenir 1 000 sociétés.
import { Ban, ChevronRight, EyeOff } from "lucide-react";
import { memo } from "react";

import { LIBELLE_INCONNU, type Noeud as NoeudArbre, libelleConfiance, sirenFr } from "@/lib/cartos/arbre";

import { Preuve } from "./preuve";

export type PropsNoeud = {
  noeud: NoeudArbre;
  niveau: number;
  position: number;
  taille: number;
  ouverts: ReadonlySet<string>;
  /** L'élément actif de l'arbre (le seul avec tabIndex 0). */
  actif: string;
  /** Préfixe des id du DOM, unique par arbre. */
  prefixe: string;
  /** Pour chaque nœud, l'ensemble de ses ancêtres (stable pour un arbre donné). */
  ancetres: ReadonlyMap<string, ReadonlySet<string>>;
};

export const idDom = (prefixe: string, id: string) => `${prefixe}-${id}`;

const BADGE = "inline-flex w-fit items-center gap-1 rounded-md border px-1.5 py-0.5 break-words";

function pluriel(n: number, mot: string) {
  return `${n.toLocaleString("fr-FR")} ${mot}${n > 1 ? "s" : ""}`;
}

function Fiche({ noeud, niveau, idDescription }: { noeud: NoeudArbre; niveau: number; idDescription: string }) {
  const s = noeud.societe;
  const enDessous =
    noeud.descendants > 0 ? (
      <span className="text-muted-foreground">{pluriel(noeud.descendants, "société")} en dessous</span>
    ) : null;

  if (!s) {
    return (
      <div id={idDescription} className="flex flex-col gap-1 text-sm">
        <p className="text-muted-foreground">
          Sociétés retenues dont la maison mère n&apos;est pas dans la carto.
        </p>
        {enDessous}
      </div>
    );
  }

  return (
    <div id={idDescription} className="flex flex-col gap-1.5 text-sm">
      <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-muted-foreground">
        <span>
          SIREN{" "}
          <span className="font-mono whitespace-nowrap text-foreground tabular-nums">{sirenFr(s.siren)}</span>
        </span>
        <span>Niveau {s.niveau}</span>
        {noeud.maisonMere ? (
          <span className="break-words">
            Maison mère : {noeud.maisonMere.nom ?? "nom inconnu"} ({sirenFr(noeud.maisonMere.siren)})
          </span>
        ) : niveau > 1 ? (
          <span>Maison mère hors de la carto{s.maison_mere_siren ? ` (${sirenFr(s.maison_mere_siren)})` : ""}</span>
        ) : null}
        {enDessous}
      </p>
      <p className="flex flex-wrap gap-1.5">
        <span
          className={`${BADGE} ${
            s.confiance === "C"
              ? "border-amber-700/50 text-amber-900 dark:text-amber-200"
              : "border-foreground/25 text-foreground"
          }`}
        >
          Confiance : {libelleConfiance(s.confiance)}
        </span>
        <span className={`${BADGE} border-foreground/25 text-foreground`}>
          Ciblable : {s.ciblable ? "Oui" : "Non"}
          {s.raison_ciblable ? ` — ${s.raison_ciblable}` : ""}
        </span>
        {s.opposition_prospection ? (
          <span
            className={`${BADGE} border-amber-700/50 bg-amber-50 font-medium text-amber-950 dark:bg-amber-950/40 dark:text-amber-100`}
          >
            <Ban aria-hidden="true" className="size-3.5 shrink-0" />
            Opposition à la prospection
          </span>
        ) : null}
        {s.non_diffusible ? (
          <span className={`${BADGE} border-foreground/40 font-medium text-foreground`}>
            <EyeOff aria-hidden="true" className="size-3.5 shrink-0" />
            Non diffusible (INSEE)
          </span>
        ) : null}
      </p>
    </div>
  );
}

function NoeudBrut({ noeud, niveau, position, taille, ouverts, actif, prefixe, ancetres }: PropsNoeud) {
  const id = idDom(prefixe, noeud.id);
  const aDesEnfants = noeud.enfants.length > 0;
  const ouvert = aDesEnfants && ouverts.has(noeud.id);
  const estActif = actif === noeud.id;
  const nom = noeud.societe ? (noeud.societe.nom ?? "Nom inconnu") : LIBELLE_INCONNU;

  return (
    // Pas d'aria-selected : l'arbre n'a pas de sélection, seulement un focus
    // (ARIA 1.2 ne l'exige plus sur treeitem ; « sélectionné » à chaque société
    // serait du bruit pour un lecteur d'écran).
    <li
      id={id}
      // eslint-disable-next-line jsx-a11y/role-has-required-aria-props
      role="treeitem"
      data-noeud={noeud.id}
      aria-level={niveau}
      aria-setsize={taille}
      aria-posinset={position}
      aria-expanded={aDesEnfants ? ouvert : undefined}
      aria-labelledby={`${id}-nom`}
      aria-describedby={`${id}-fiche`}
      tabIndex={estActif ? 0 : -1}
      className="group/noeud min-w-0 outline-none [&:focus-visible>[data-carte]]:ring-3 [&:focus-visible>[data-carte]]:ring-ring"
    >
      <div data-carte="" className="flex min-w-0 gap-1 rounded-lg py-1 pr-2">
        {aDesEnfants ? (
          <span
            data-bascule={noeud.id}
            aria-hidden="true"
            className="flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-md hover:bg-muted md:size-8"
          >
            <ChevronRight className={`size-4 transition-transform ${ouvert ? "rotate-90" : ""}`} />
          </span>
        ) : (
          <span aria-hidden="true" className="size-11 shrink-0 md:size-8" />
        )}
        <div className="flex min-w-0 flex-1 flex-col gap-1 pt-2.5 md:pt-1">
          <p id={`${id}-nom`} className="font-medium break-words">
            {nom}
          </p>
          <Fiche noeud={noeud} niveau={niveau} idDescription={`${id}-fiche`} />
          {noeud.societe ? <Preuve texte={noeud.societe.preuve} focusable={estActif} /> : null}
        </div>
      </div>
      {ouvert ? (
        <ul role="group" className="ml-3 border-l border-foreground/20 pl-0.5 sm:ml-5 sm:pl-3 md:ml-4">
          {noeud.enfants.map((enfant, i) => (
            <Noeud
              key={enfant.id}
              noeud={enfant}
              niveau={niveau + 1}
              position={i + 1}
              taille={noeud.enfants.length}
              ouverts={ouverts}
              actif={actif}
              prefixe={prefixe}
              ancetres={ancetres}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/** `id` est dans le sous-arbre de `racine` (lui-même compris). */
function dansLeSousArbre(racine: string, id: string, ancetres: ReadonlyMap<string, ReadonlySet<string>>) {
  return id === racine || (ancetres.get(id)?.has(racine) ?? false);
}

/** Un nœud ne se redessine que si l'élément actif entre dans son sous-arbre ou en sort, ou si un nœud s'ouvre ou se ferme. */
export const Noeud = memo(NoeudBrut, (avant, apres) => {
  if (
    avant.noeud !== apres.noeud ||
    avant.niveau !== apres.niveau ||
    avant.position !== apres.position ||
    avant.taille !== apres.taille ||
    avant.ouverts !== apres.ouverts ||
    avant.prefixe !== apres.prefixe ||
    avant.ancetres !== apres.ancetres
  ) {
    return false;
  }
  if (avant.actif === apres.actif) return true;
  const id = avant.noeud.id;
  return !dansLeSousArbre(id, avant.actif, avant.ancetres) && !dansLeSousArbre(id, apres.actif, apres.ancetres);
});
