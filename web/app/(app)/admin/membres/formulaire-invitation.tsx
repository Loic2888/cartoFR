"use client";

import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { inviterMembre, type EtatInvitation } from "./actions";

export function FormulaireInvitation() {
  const [etat, inviter, enCours] = useActionState<EtatInvitation, FormData>(inviterMembre, {
    statut: "initial",
  });

  return (
    <form action={inviter} className="flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-2">
        <Label htmlFor="email-invitation">Adresse e-mail du nouveau membre</Label>
        <Input
          id="email-invitation"
          name="email"
          type="email"
          autoComplete="off"
          inputMode="email"
          required
          aria-invalid={etat.statut === "erreur" ? true : undefined}
          aria-describedby="invitation-etat"
        />
      </div>
      <div id="invitation-etat" aria-live="polite">
        {etat.statut === "erreur" ? (
          <p
            role="alert"
            className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            <span className="font-medium">Erreur : </span>
            {etat.message}
          </p>
        ) : null}
        {etat.statut === "envoye" ? (
          <p className="rounded-lg border px-3 py-2 text-sm">
            Invitation envoyée à <span className="font-medium break-all">{etat.email}</span>. Le
            membre se connecte en ouvrant le lien reçu.
          </p>
        ) : null}
      </div>
      <Button type="submit" disabled={enCours} className="w-full md:w-auto md:self-start">
        {enCours ? "Envoi en cours…" : "Envoyer l'invitation"}
      </Button>
    </form>
  );
}
