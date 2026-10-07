// Membres de l'organisation et invitation (T009), réservé aux admins.
import type { Metadata } from "next";

import { organisationAdministree, utilisateurCourant } from "@/lib/session";
import { creerClientAdmin } from "@/lib/supabase/admin";

import { FormulaireInvitation } from "./formulaire-invitation";

export const metadata: Metadata = { title: "Membres · cartoFR" };

const ROLES: Record<string, string> = { admin: "Administrateur", membre: "Membre" };

const dateFr = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "Europe/Paris",
});

export default async function Membres() {
  const { supabase, user } = await utilisateurCourant();
  const organisationId = await organisationAdministree(supabase, user.id);

  if (!organisationId) {
    return (
      <main className="flex flex-1 flex-col gap-4 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
        <h1 className="text-2xl font-semibold tracking-tight">Membres</h1>
        <p className="text-base">
          Cette page est réservée aux administrateurs de l&apos;organisation.
        </p>
      </main>
    );
  }

  // Liste lue avec la session de l'admin : RLS limite à ses organisations.
  const [{ data: organisation }, { data: membres }] = await Promise.all([
    supabase.from("organisations").select("nom").eq("id", organisationId).maybeSingle(),
    supabase
      .from("membres")
      .select("user_id, role, cree_le")
      .eq("organisation_id", organisationId)
      .order("cree_le", { ascending: true }),
  ]);

  // Les adresses sont dans auth.users, hors de portée de RLS : lues avec la
  // clé service_role, pour ces seuls membres, une fois le rôle admin vérifié.
  const admin = creerClientAdmin();
  const lignes = await Promise.all(
    (membres ?? []).map(async (m) => {
      const { data } = await admin.auth.admin.getUserById(m.user_id as string);
      return {
        id: m.user_id as string,
        email: data.user?.email ?? "Adresse indisponible",
        role: ROLES[m.role as string] ?? (m.role as string),
        depuis: dateFr.format(new Date(m.cree_le as string)),
        enAttente: !data.user?.last_sign_in_at,
      };
    }),
  );

  return (
    <main className="flex flex-1 flex-col gap-8 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Membres</h1>
        {organisation?.nom ? (
          <p className="text-sm text-muted-foreground">{organisation.nom as string}</p>
        ) : null}
      </div>

      <section aria-labelledby="titre-inviter" className="flex flex-col gap-4">
        <h2 id="titre-inviter" className="text-lg font-medium">
          Inviter un membre
        </h2>
        <p className="text-sm text-muted-foreground">
          Le nouveau membre reçoit un e-mail avec un lien pour se connecter. Seule son adresse est
          demandée.
        </p>
        <div className="md:max-w-md">
          <FormulaireInvitation />
        </div>
      </section>

      <section aria-labelledby="titre-liste" className="flex flex-col gap-4">
        <h2 id="titre-liste" className="text-lg font-medium">
          {lignes.length} {lignes.length > 1 ? "membres" : "membre"}
        </h2>
        <ul className="flex flex-col gap-2">
          {lignes.map((l) => (
            <li key={l.id} className="flex flex-col gap-1 rounded-lg border px-3 py-2">
              <span className="font-medium break-all">{l.email}</span>
              <span className="text-sm text-muted-foreground">
                {l.role} · depuis le {l.depuis}
                {l.enAttente ? " · invitation pas encore acceptée" : ""}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
