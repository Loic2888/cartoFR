// État du registre (T014, FR-003), réservé aux admins : date des données,
// dernier passage de la synchro, statut, volumes et cause d'un échec.
// Lecture seule, avec la session de l'utilisateur (RLS), jamais service_role.
import type { Metadata } from "next";

import { EtatRegistre } from "@/components/etat-registre";
import type { LigneEtatRegistre } from "@/lib/etat-registre";
import { organisationAdministree, utilisateurCourant } from "@/lib/session";

export const metadata: Metadata = { title: "État du registre · cartoFR" };

const MAIN = "flex flex-1 flex-col gap-6 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8";

export default async function Registre() {
  const { supabase, user } = await utilisateurCourant();
  const organisationId = await organisationAdministree(supabase, user.id);

  if (!organisationId) {
    return (
      <main className={MAIN}>
        <h1 className="text-2xl font-semibold tracking-tight">État du registre</h1>
        <p className="text-base">
          Cette page est réservée aux administrateurs de l&apos;organisation.
        </p>
      </main>
    );
  }

  const { data, error } = await supabase
    .from("etat_registre")
    .select("source, date_donnees, dernier_passage, statut, volumes, erreur");

  return (
    <main className={MAIN}>
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">État du registre</h1>
        <p className="text-sm text-muted-foreground">
          La synchro de nuit met à jour la base avec l&apos;INPI et l&apos;INSEE. Les données ne
          doivent pas avoir plus de 7 jours de retard sur le registre.
        </p>
      </div>
      {error ? (
        <p role="alert" className="rounded-lg border border-red-700/40 px-3 py-2 text-sm">
          L&apos;état du registre n&apos;a pas pu être lu. Rechargez la page dans un instant.
        </p>
      ) : (
        <EtatRegistre lignes={(data ?? []) as LigneEtatRegistre[]} maintenant={new Date()} />
      )}
    </main>
  );
}
