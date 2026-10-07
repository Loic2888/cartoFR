// Groupes de l'organisation (T019). Lus avec la session (RLS) : un membre ne
// voit que les groupes de son organisation.
import type { Metadata } from "next";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { utilisateurCourant } from "@/lib/session";

import { SANS_ORGANISATION, dateFr, organisationMembre } from "./organisation";

export const metadata: Metadata = { title: "Groupes · cartoFR" };

export default async function Groupes() {
  const { supabase, user } = await utilisateurCourant();
  const organisationId = await organisationMembre(supabase, user.id);

  if (!organisationId) {
    return (
      <main className="flex flex-1 flex-col gap-4 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
        <h1 className="text-2xl font-semibold tracking-tight">Groupes</h1>
        <p className="text-base">{SANS_ORGANISATION}</p>
      </main>
    );
  }

  const { data: groupes, error } = await supabase
    .from("groupes")
    .select("id, nom, tete_siren, cree_le")
    .eq("organisation_id", organisationId)
    .order("nom", { ascending: true });

  return (
    <main className="flex flex-1 flex-col gap-6 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Groupes</h1>
        <Link href="/groupes/nouveau" className={buttonVariants({ className: "w-full sm:w-auto" })}>
          Nouveau groupe
        </Link>
      </div>

      {error ? (
        <p
          role="alert"
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          <span className="font-medium">Erreur : </span>
          Les groupes n&apos;ont pas pu être lus. Rechargez la page dans un instant.
        </p>
      ) : !groupes || groupes.length === 0 ? (
        <div className="flex flex-col gap-2 rounded-xl border border-dashed p-6">
          <p className="font-medium">Aucun groupe pour l&apos;instant.</p>
          <p className="text-sm text-muted-foreground">
            Créez-en un en choisissant sa société de tête : cherchez-la par son nom ou son SIREN.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {groupes.map((g) => (
            <li key={g.id as string}>
              <Link
                href={`/groupes/${g.id as string}`}
                className="flex min-h-11 flex-col gap-1 rounded-lg border px-3 py-2 outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring"
              >
                <span className="font-medium break-words">{g.nom as string}</span>
                <span className="text-sm text-muted-foreground">
                  SIREN <span className="font-mono tabular-nums">{g.tete_siren as string}</span> · créé
                  le {dateFr.format(new Date(g.cree_le as string))}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
