"use client";

import Link from "next/link";
import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MOT_DE_CONFIRMATION, type EtatSuppression } from "@/lib/compte/suppression";

import { supprimerMonCompte } from "./actions";

/** Confirmation explicite : le mot SUPPRIMER tapé à la main. Le bouton est
 * désactivé pendant l'envoi (double clic). Marche aussi sans JavaScript. */
export function FormulaireSuppression() {
  const [etat, supprimer, enCours] = useActionState<EtatSuppression, FormData>(supprimerMonCompte, {
    statut: "initial",
  });

  return (
    <form action={supprimer} className="flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-2">
        <Label htmlFor="confirmation-suppression">
          Pour confirmer, tapez {MOT_DE_CONFIRMATION} en lettres capitales
        </Label>
        <Input
          id="confirmation-suppression"
          name="confirmation"
          type="text"
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          required
          className="h-11"
          aria-invalid={etat.statut === "erreur" ? true : undefined}
          aria-describedby="suppression-etat"
        />
      </div>
      <div id="suppression-etat" aria-live="polite">
        {etat.statut === "erreur" ? (
          <p
            role="alert"
            className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            <span className="font-medium">Erreur : </span>
            {etat.message}
            {etat.session ? (
              <>
                {" "}
                <Link
                  href="/connexion"
                  className="inline-flex min-h-11 items-center font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring"
                >
                  Se reconnecter
                </Link>
              </>
            ) : null}
          </p>
        ) : null}
      </div>
      <Button
        type="submit"
        variant="destructive"
        disabled={enCours}
        className="h-11 w-full md:h-11 md:w-auto md:self-start"
      >
        {enCours ? "Suppression en cours…" : "Supprimer définitivement mon compte"}
      </Button>
    </form>
  );
}
