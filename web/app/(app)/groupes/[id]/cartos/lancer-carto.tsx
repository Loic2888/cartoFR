"use client";

// Bouton « Lancer la carto » et rafraîchissement de la liste (T021).
// Le droit de lancer se décide côté serveur (cartos/actions.ts) : ici, le
// bouton n'est qu'actif ou non, avec la raison écrite à côté. Tant qu'une
// carto est en attente ou en cours, la page se rafraîchit toutes les 3 s.
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import type { Resultat } from "@/lib/cartos/operations";

import { lancerCarto } from "./actions";

export const RAFRAICHISSEMENT_MS = 3000;

type Props = {
  groupeId: string;
  /** Raison pour laquelle on ne peut pas lancer, déjà en français ; null si on peut. */
  empechement: string | null;
  /** Lien vers les réglages, montré quand aucune version n'est validée. */
  lienReglages: React.ReactNode;
  /** Une carto du groupe tourne : la page se rafraîchit. */
  actif: boolean;
};

export function LancerCarto({ groupeId, empechement, lienReglages, actif }: Props) {
  const router = useRouter();
  const [resultat, setResultat] = useState<Resultat | null>(null);
  const [enCours, demarrer] = useTransition();

  useEffect(() => {
    if (!actif) return;
    const minuterie = setInterval(() => router.refresh(), RAFRAICHISSEMENT_MS);
    return () => clearInterval(minuterie);
  }, [actif, router]);

  function lancer() {
    demarrer(async () => {
      const r = await lancerCarto({ groupeId });
      setResultat(r);
      router.refresh();
    });
  }

  return (
    <div className="flex flex-col gap-3">
      <Button
        type="button"
        onClick={lancer}
        disabled={enCours || empechement !== null}
        aria-describedby={empechement ? "carto-empechement" : undefined}
        className="w-full sm:w-auto sm:self-start"
      >
        {enCours ? "Lancement…" : "Lancer la carto"}
      </Button>
      {empechement ? (
        <p id="carto-empechement" className="text-sm text-muted-foreground">
          {empechement} {lienReglages}
        </p>
      ) : null}
      <div aria-live="polite" className="empty:absolute">
        {resultat?.statut === "erreur" ? (
          <p
            role="alert"
            className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            <span className="font-medium">Erreur : </span>
            {resultat.message}
          </p>
        ) : resultat?.statut === "ok" ? (
          <p className="rounded-lg border px-3 py-2 text-sm">{resultat.message}</p>
        ) : null}
      </div>
    </div>
  );
}
