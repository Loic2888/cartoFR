// Mon compte (T031, règle produit 4) : ce que cartoFR garde sur le membre, et
// la suppression de son compte, avec confirmation explicite. Mobile d'abord.
import type { Metadata } from "next";

import { type Appartenance, type Consequence, consequences } from "@/lib/compte/suppression";
import { utilisateurCourant } from "@/lib/session";

import { FormulaireSuppression } from "./formulaire-suppression";

export const metadata: Metadata = { title: "Mon compte · cartoFR" };

const ROLES: Record<string, string> = { admin: "administrateur", membre: "membre" };

const EFFETS: Record<Consequence["cas"], string> = {
  rien: "Ses groupes et ses cartos restent à l'organisation.",
  promotion:
    "Vous êtes son seul administrateur : le membre le plus ancien deviendra administrateur. Ses groupes et ses cartos restent à l'organisation.",
  sans_membre:
    "Vous en êtes le dernier membre : l'organisation, ses groupes et ses cartos sont gardés, sans membre. Seul l'opérateur de cartoFR pourra y inviter quelqu'un ou la supprimer.",
};

export default async function Compte() {
  const { supabase, user } = await utilisateurCourant();

  // Lu avec la session (RLS) : les appartenances de ses organisations seulement.
  const [{ data: membres }, { data: organisations }] = await Promise.all([
    supabase.from("membres").select("organisation_id, user_id, role, cree_le"),
    supabase.from("organisations").select("id, nom"),
  ]);
  const appartenances: Appartenance[] = (membres ?? []).map((m) => ({
    organisationId: m.organisation_id as string,
    userId: m.user_id as string,
    role: m.role as string,
    creeLe: m.cree_le as string,
  }));
  const noms = new Map((organisations ?? []).map((o) => [o.id as string, o.nom as string]));
  const roles = new Map(
    appartenances.filter((m) => m.userId === user.id).map((m) => [m.organisationId, m.role]),
  );
  const lignes = consequences(appartenances, user.id).map((c) => ({
    id: c.organisationId,
    nom: noms.get(c.organisationId) ?? "Organisation",
    role: ROLES[roles.get(c.organisationId) ?? ""] ?? "membre",
    effet: EFFETS[c.cas],
  }));

  return (
    <main className="flex flex-1 flex-col gap-8 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <h1 className="text-2xl font-semibold tracking-tight">Mon compte</h1>

      <section aria-labelledby="titre-donnees" className="flex flex-col gap-3">
        <h2 id="titre-donnees" className="text-lg font-medium">
          Ce que cartoFR garde sur vous
        </h2>
        <p className="text-base">
          Votre adresse e-mail : <span className="font-medium break-all">{user.email}</span>. Elle
          sert seulement à vous envoyer les liens de connexion. Aucun nom, aucune fonction.
        </p>
        <p className="text-sm text-muted-foreground">
          Les groupes, réglages et cartos que vous créez appartiennent à votre organisation.
        </p>
      </section>

      <section aria-labelledby="titre-supprimer" className="flex flex-col gap-4 md:max-w-xl">
        <h2 id="titre-supprimer" className="text-lg font-medium">
          Supprimer mon compte
        </h2>
        <p className="text-base">
          La suppression est définitive. Votre adresse e-mail est effacée et vous ne pourrez plus
          vous connecter. Pour revenir, il faudra une nouvelle invitation.
        </p>
        <p className="text-base">
          Vos cartos ne sont pas supprimées : elles restent à votre organisation, sans votre adresse
          ni aucune mention de votre compte.
        </p>
        {lignes.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {lignes.map((l) => (
              <li key={l.id} className="flex flex-col gap-1 rounded-lg border px-3 py-2">
                <span className="font-medium break-words">
                  {l.nom} <span className="font-normal text-muted-foreground">· {l.role}</span>
                </span>
                <span className="text-sm">{l.effet}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <FormulaireSuppression />
      </section>
    </main>
  );
}
