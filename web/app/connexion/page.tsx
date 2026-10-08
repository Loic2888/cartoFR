// Page de connexion (T009) : un seul champ, l'e-mail, et un lien magique.
import type { Metadata } from "next";

import { messageErreurAuth } from "@/lib/erreurs";

import { FormulaireConnexion } from "./formulaire-connexion";

export const metadata: Metadata = { title: "Connexion · cartoFR" };

export default async function Connexion({ searchParams }: PageProps<"/connexion">) {
  // `erreur` vient de /auth/callback (lien expiré, invalide…). Seul le message
  // traduit est affiché, jamais le paramètre lui-même.
  const { erreur, compte } = await searchParams;
  const erreurDuLien = typeof erreur === "string" ? messageErreurAuth(erreur) : undefined;
  // Retour de /compte après la suppression d'un compte (T031).
  const compteSupprime = compte === "supprime";

  return (
    <main className="flex flex-1 flex-col justify-center px-4 py-8">
      <div className="mx-auto flex w-full max-w-sm flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">Connexion à cartoFR</h1>
          <p className="text-sm text-muted-foreground">
            Saisissez votre adresse e-mail : vous recevrez un lien pour vous connecter, sans mot de
            passe. L&apos;accès se fait sur invitation.
          </p>
        </div>
        {compteSupprime ? (
          <p role="status" className="rounded-lg border px-3 py-2 text-sm">
            Votre compte a été supprimé, et votre adresse e-mail effacée. Vos cartos restent à votre
            organisation.
          </p>
        ) : null}
        <FormulaireConnexion erreurDuLien={erreurDuLien} />
      </div>
    </main>
  );
}
