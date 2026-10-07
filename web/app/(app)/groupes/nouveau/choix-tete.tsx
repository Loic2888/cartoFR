"use client";

// Bouton « Créer le groupe » d'un résultat (T019). Une tête cessée ou radiée
// demande de cocher une confirmation, vérifiée côté serveur : pas d'attribut
// `required`, dont la bulle du navigateur serait en anglais (règle produit 1).
import Link from "next/link";
import { useActionState, useId } from "react";

import { Button } from "@/components/ui/button";

import { creerGroupe, type EtatCreation } from "../actions";

type Props = {
  siren: string;
  nom: string;
  /** Libellé du statut si la société n'est pas active (« Cessée », « Radiée »). */
  inactive: string | null;
};

export function ChoixTete({ siren, nom, inactive }: Props) {
  const [etat, creer, enCours] = useActionState<EtatCreation, FormData>(creerGroupe, {
    statut: "initial",
  });
  const id = useId();

  return (
    <form action={creer} className="flex flex-col gap-3">
      <input type="hidden" name="siren" value={siren} />
      {inactive ? (
        <div className="flex flex-col gap-2 rounded-lg border border-amber-600/50 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
          <p>
            <span className="font-semibold">Attention : </span>
            cette société est {inactive.toLowerCase()}. Ses filiales actuelles peuvent dépendre
            d&apos;une autre tête.
          </p>
          <label htmlFor={`${id}-confirmation`} className="flex min-h-11 items-center gap-3">
            <input
              id={`${id}-confirmation`}
              type="checkbox"
              name="confirmation"
              value="oui"
              aria-describedby={`${id}-etat`}
              className="size-5 shrink-0 accent-primary outline-none focus-visible:ring-3 focus-visible:ring-ring"
            />
            <span>Je confirme vouloir en faire la tête du groupe</span>
          </label>
        </div>
      ) : null}
      <div aria-live="polite" id={`${id}-etat`}>
        {etat.statut === "erreur" ? (
          <p
            role="alert"
            className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            <span className="font-medium">Erreur : </span>
            {etat.message}
          </p>
        ) : null}
        {etat.statut === "doublon" ? (
          <p role="alert" className="rounded-lg border px-3 py-2 text-sm">
            {etat.message}{" "}
            {etat.groupeId ? (
              <Link
                href={`/groupes/${etat.groupeId}`}
                className="inline-flex min-h-11 items-center font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring md:min-h-0"
              >
                Ouvrir le groupe existant
              </Link>
            ) : null}
          </p>
        ) : null}
      </div>
      <Button
        type="submit"
        disabled={enCours}
        aria-describedby={`${id}-etat`}
        aria-label={`Créer le groupe avec ${nom} pour tête`}
        className="w-full md:w-auto md:self-start"
      >
        {enCours ? "Création en cours…" : "Créer le groupe"}
      </Button>
    </form>
  );
}
