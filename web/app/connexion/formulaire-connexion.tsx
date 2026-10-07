"use client";

import { useActionState, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { envoyerLien, type EtatEnvoi } from "./actions";

/** Formulaire du lien magique. Marche aussi sans JavaScript (Server Action). */
export function FormulaireConnexion({ erreurDuLien }: { erreurDuLien?: string }) {
  // Changer la clé remonte le formulaire : retour à l'état initial.
  const [cle, setCle] = useState(0);
  return (
    <Formulaire
      key={cle}
      erreurDuLien={cle === 0 ? erreurDuLien : undefined}
      recommencer={() => setCle((c) => c + 1)}
    />
  );
}

function Formulaire({
  erreurDuLien,
  recommencer,
}: {
  erreurDuLien?: string;
  recommencer: () => void;
}) {
  const [etat, envoyer, enCours] = useActionState<EtatEnvoi, FormData>(envoyerLien, {
    statut: "initial",
  });

  if (etat.statut === "envoye") {
    return (
      <div role="status" className="flex flex-col gap-3">
        <p className="text-base font-medium">Vérifiez votre boîte mail.</p>
        <p className="text-sm text-muted-foreground">
          Si cette adresse a un compte cartoFR, un lien de connexion vient de lui être envoyé. Il
          ne sert qu&apos;une fois.
        </p>
        <p className="text-sm text-muted-foreground">
          Rien reçu ? Regardez dans les indésirables et vérifiez l&apos;adresse. Si vous venez
          d&apos;être invité, ouvrez d&apos;abord le lien de l&apos;e-mail d&apos;invitation ; sinon,
          demandez une invitation à l&apos;administrateur de votre organisation.
        </p>
        <Button type="button" variant="outline" className="w-full md:w-auto" onClick={recommencer}>
          Saisir une autre adresse
        </Button>
      </div>
    );
  }

  const erreur = etat.statut === "erreur" ? etat.message : erreurDuLien;

  return (
    <form action={envoyer} className="flex flex-col gap-4" noValidate>
      {erreur ? (
        <p
          id="connexion-erreur"
          role="alert"
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          <span className="font-medium">Erreur : </span>
          {erreur}
        </p>
      ) : null}
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Adresse e-mail professionnelle</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          required
          aria-invalid={etat.statut === "erreur" ? true : undefined}
          aria-describedby={erreur ? "connexion-erreur" : undefined}
        />
      </div>
      <Button type="submit" disabled={enCours} className="w-full">
        {enCours ? "Envoi en cours…" : "Recevoir un lien de connexion"}
      </Button>
    </form>
  );
}
