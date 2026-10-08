"use client";

// Proposition des réglages par l'IA (T026, FR-008, SC-007) : le bouton
// « Proposer », puis la revue élément par élément.
//
// Chaque élément affiche sa source (C1) et se garde, se corrige ou se rejette ;
// le consultant peut aussi ajouter ce qui manque. « Valider » crée et valide
// une nouvelle version, avec le nombre de corrections (C2). Une colonne,
// cibles de 44 px, un <label> par champ, tout au clavier, focus visible.
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { Resultat } from "@/lib/reglages/operations";
import {
  type Ajout,
  type Decision,
  type Element,
  LIBELLES_LISTES,
  LISTES_PROPOSEES,
  type ListeProposee,
  appliquerRevue,
  sourceSure,
} from "@/lib/reglages/proposition";

import { demanderProposition, validerProposition } from "./actions-proposition";

const CHAMP =
  "min-h-11 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-2 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring md:text-sm dark:bg-input/30";

const CHOIX = [
  { valeur: "accepter", libelle: "Garder" },
  { valeur: "corriger", libelle: "Corriger" },
  { valeur: "rejeter", libelle: "Rejeter" },
] as const;

function Message({ resultat }: { resultat: Resultat | null }) {
  if (!resultat) return null;
  if (resultat.statut === "erreur") {
    return (
      <p
        role="alert"
        className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
      >
        <span className="font-medium">Erreur : </span>
        {resultat.message}
      </p>
    );
  }
  return <p className="rounded-lg border px-3 py-2 text-sm">{resultat.message}</p>;
}

function corrections(n: number): string {
  return n === 0 ? "Aucune correction" : n === 1 ? "1 correction" : `${n} corrections`;
}

/** Le bouton « Proposer » et l'état du dernier travail. */
export function DemandeProposition({
  groupeId,
  etat,
  enCours: travailEnCours,
}: {
  groupeId: string;
  etat: string | null;
  enCours: boolean;
}) {
  const [resultat, setResultat] = useState<Resultat | null>(null);
  const [enCours, demarrer] = useTransition();
  const bloque = enCours || travailEnCours || resultat?.statut === "ok";

  return (
    <section aria-labelledby="titre-proposer" className="flex flex-col gap-3 rounded-lg border px-4 py-3">
      <h2 id="titre-proposer" className="text-lg font-medium">
        Proposition par l&apos;IA
      </h2>
      <p className="text-sm text-muted-foreground">
        L&apos;IA lit le site et le rapport annuel du groupe et propose des marques, des sigles, des
        maisons et des exclusions, chacun avec sa source. Elle ne reçoit que des données de sociétés.
        Rien n&apos;est utilisé avant votre revue et votre validation.
      </p>
      {etat ? <p className="text-sm font-medium">{etat}</p> : null}
      <div aria-live="polite" className="empty:absolute">
        <Message resultat={resultat} />
      </div>
      <Button
        type="button"
        disabled={bloque}
        className="w-full md:w-auto md:self-start"
        onClick={() =>
          demarrer(async () => {
            setResultat(await demanderProposition({ groupeId }));
          })
        }
      >
        {enCours ? "Demande en cours…" : "Proposer des réglages"}
      </Button>
    </section>
  );
}

type Saisie = { choix: Decision["choix"]; valeur: string; liste: ListeProposee };

function decision(s: Saisie): Decision {
  return s.choix === "corriger" ? { choix: "corriger", valeur: s.valeur, liste: s.liste } : { choix: s.choix };
}

/** La revue d'une proposition : un bloc par élément, les ajouts, la validation. */
export function RevueProposition({
  groupeId,
  version,
  elements,
  contenu,
}: {
  groupeId: string;
  version: number;
  elements: Element[];
  contenu: Record<string, unknown>;
}) {
  const [saisies, setSaisies] = useState<Saisie[]>(() =>
    elements.map((e) => ({ choix: "accepter", valeur: e.valeur, liste: e.liste })),
  );
  const [ajouts, setAjouts] = useState<Ajout[]>([]);
  const [listeAjout, setListeAjout] = useState<ListeProposee>("marques_sures");
  const [valeurAjout, setValeurAjout] = useState("");
  const [resultat, setResultat] = useState<Resultat | null>(null);
  const [enCours, demarrer] = useTransition();

  const decisions = saisies.map(decision);
  const apercu = appliquerRevue(contenu, elements, decisions, ajouts);
  const n = apercu.ok ? apercu.corrections : null;

  function changer(i: number, partiel: Partial<Saisie>) {
    setSaisies((s) => s.map((x, j) => (j === i ? { ...x, ...partiel } : x)));
  }

  function ajouter() {
    const valeur = valeurAjout.trim();
    if (!valeur) return;
    setAjouts((a) => [...a, { liste: listeAjout, valeur }]);
    setValeurAjout("");
  }

  function valider(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    demarrer(async () => {
      setResultat(await validerProposition({ groupeId, version, decisions, ajouts }));
    });
  }

  return (
    <form onSubmit={valider} aria-labelledby="titre-revue" className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 id="titre-revue" className="text-lg font-medium">
          Revoir la proposition (version {version})
        </h2>
        <p className="text-sm text-muted-foreground">
          Pour chaque élément, ouvrez sa source, puis gardez-le, corrigez-le ou rejetez-le. Une
          marque qui a des homonymes au registre est rangée en marque ambiguë : le moteur exigera une
          deuxième preuve.
        </p>
      </div>

      {elements.length === 0 ? (
        <p className="text-sm">L&apos;IA n&apos;a proposé aucun élément sourcé. Ajoutez-les ci-dessous.</p>
      ) : (
        <ol className="flex flex-col gap-4">
          {elements.map((e, i) => {
            const s = saisies[i];
            const id = `element-${i}`;
            const url = sourceSure(e.source);
            return (
              <li key={id}>
                <fieldset className="flex flex-col gap-3 rounded-lg border px-4 py-3">
                  <legend className="px-1 font-medium break-words">{e.valeur}</legend>
                  <p className="text-sm text-muted-foreground">
                    Proposé en : {LIBELLES_LISTES[e.liste]}
                    {e.homonymes != null && e.liste.startsWith("marques_")
                      ? e.homonymes === 0
                        ? " · aucun homonyme au registre"
                        : ` · ${e.homonymes} homonyme${e.homonymes > 1 ? "s" : ""} au registre`
                      : null}
                  </p>
                  <p className="text-sm break-all">
                    Source :{" "}
                    {url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex min-h-11 items-center rounded underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring"
                      >
                        {url}
                        <span className="sr-only"> (s&apos;ouvre dans un nouvel onglet)</span>
                      </a>
                    ) : (
                      <span>{e.source} (adresse non sûre, non cliquable)</span>
                    )}
                  </p>
                  <div role="radiogroup" aria-label={`Décision pour ${e.valeur}`} className="flex flex-col gap-1 sm:flex-row sm:gap-4">
                    {CHOIX.map((c) => (
                      <label key={c.valeur} className="flex min-h-11 items-center gap-3 text-sm">
                        <input
                          type="radio"
                          name={`${id}-choix`}
                          value={c.valeur}
                          checked={s.choix === c.valeur}
                          onChange={() => changer(i, { choix: c.valeur })}
                          className="size-5 shrink-0 accent-primary outline-none focus-visible:ring-3 focus-visible:ring-ring"
                        />
                        {c.libelle}
                      </label>
                    ))}
                  </div>
                  {s.choix === "corriger" ? (
                    <div className="flex flex-col gap-3">
                      <div className="flex flex-col gap-2">
                        <Label htmlFor={`${id}-valeur`}>Valeur corrigée</Label>
                        <input
                          id={`${id}-valeur`}
                          type="text"
                          value={s.valeur}
                          onChange={(ev) => changer(i, { valeur: ev.target.value })}
                          // Entrée ne valide pas toute la revue par mégarde.
                          onKeyDown={(ev) => {
                            if (ev.key === "Enter") ev.preventDefault();
                          }}
                          autoComplete="off"
                          spellCheck={false}
                          className={CHAMP}
                        />
                      </div>
                      <div className="flex flex-col gap-2">
                        <Label htmlFor={`${id}-liste`}>Liste</Label>
                        <select
                          id={`${id}-liste`}
                          value={s.liste}
                          onChange={(ev) => changer(i, { liste: ev.target.value as ListeProposee })}
                          className={CHAMP}
                        >
                          {LISTES_PROPOSEES.map((l) => (
                            <option key={l} value={l}>
                              {LIBELLES_LISTES[l]}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ) : null}
                </fieldset>
              </li>
            );
          })}
        </ol>
      )}

      <fieldset className="flex flex-col gap-3 rounded-lg border px-4 py-3">
        <legend className="px-1 text-sm font-medium">Ajouter ce qui manque</legend>
        <div className="flex flex-col gap-2">
          <Label htmlFor="ajout-liste">Liste</Label>
          <select
            id="ajout-liste"
            value={listeAjout}
            onChange={(ev) => setListeAjout(ev.target.value as ListeProposee)}
            className={CHAMP}
          >
            {LISTES_PROPOSEES.map((l) => (
              <option key={l} value={l}>
                {LIBELLES_LISTES[l]}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="ajout-valeur">Valeur</Label>
          <input
            id="ajout-valeur"
            type="text"
            value={valeurAjout}
            onChange={(ev) => setValeurAjout(ev.target.value)}
            onKeyDown={(ev) => {
              if (ev.key === "Enter") {
                ev.preventDefault();
                ajouter();
              }
            }}
            autoComplete="off"
            spellCheck={false}
            className={CHAMP}
          />
        </div>
        <Button type="button" variant="outline" onClick={ajouter} className="w-full md:w-auto md:self-start">
          Ajouter
        </Button>
        {ajouts.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {ajouts.map((a, i) => (
              <li key={`${a.liste}-${a.valeur}-${i}`} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="break-words">
                  {a.valeur} · {LIBELLES_LISTES[a.liste]}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setAjouts((x) => x.filter((_, j) => j !== i))}
                  aria-label={`Retirer l'ajout ${a.valeur}`}
                >
                  Retirer
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
      </fieldset>

      <div className="flex flex-col gap-3">
        <p className="text-sm" aria-live="polite">
          {n === null ? "Une valeur corrigée est vide." : `${corrections(n)} de la proposition.`}
        </p>
        <div aria-live="polite" className="empty:absolute">
          <Message resultat={resultat} />
        </div>
        <Button
          type="submit"
          disabled={enCours || n === null || resultat?.statut === "ok"}
          className="w-full md:w-auto md:self-start"
        >
          {enCours ? "Validation en cours…" : "Valider ces réglages"}
        </Button>
        <p className="text-sm text-muted-foreground">
          Valider crée une nouvelle version, validée, qui servira aux prochaines cartos. La
          proposition reste dans l&apos;historique.
        </p>
      </div>
    </form>
  );
}
