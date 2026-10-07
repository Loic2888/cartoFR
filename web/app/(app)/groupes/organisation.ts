// Organisation de l'utilisateur pour les groupes (T019). Tout membre, admin ou
// non, crée et consulte les groupes de son organisation.
import "server-only";

import type { creerClientServeur } from "@/lib/supabase/server";

type Supabase = Awaited<ReturnType<typeof creerClientServeur>>;

/** Organisation dont l'utilisateur est membre (tout rôle), lue avec SA session
 * (RLS), jamais avec la clé service_role. S'il est membre de plusieurs
 * organisations, la plus ancienne (pas de choix d'organisation en V1, comme
 * organisationAdministree). Null s'il n'est membre d'aucune. */
export async function organisationMembre(supabase: Supabase, userId: string): Promise<string | null> {
  const { data, error } = await supabase
    .from("membres")
    .select("organisation_id")
    .eq("user_id", userId)
    .order("cree_le", { ascending: true })
    .limit(1)
    .maybeSingle();
  if (error || !data) return null;
  return data.organisation_id as string;
}

export const dateFr = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "Europe/Paris",
});

export const SANS_ORGANISATION =
  "Votre compte n'est rattaché à aucune organisation. Demandez une invitation à l'administrateur de votre organisation.";
