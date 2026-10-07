// Qui est connecté, et est-il admin ? (T009) Vérifié côté serveur à chaque
// page et Server Action : proxy.ts ne suffit pas à lui seul.
import "server-only";

import { redirect } from "next/navigation";
import { cache } from "react";

import { creerClientServeur } from "@/lib/supabase/server";

/** Utilisateur connecté, sinon renvoi vers /connexion. Mis en cache pour la
 * durée d'un rendu : le gabarit et la page ne font qu'un appel à GoTrue. */
export const utilisateurCourant = cache(async () => {
  const supabase = await creerClientServeur();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/connexion");
  return { supabase, user };
});

type Supabase = Awaited<ReturnType<typeof creerClientServeur>>;

/** Organisation dont l'utilisateur est admin, lue avec SA session (RLS) :
 * jamais avec la clé service_role. S'il est admin de plusieurs organisations,
 * la plus ancienne (pas de choix d'organisation en V1). Null s'il n'est admin
 * d'aucune. */
export async function organisationAdministree(
  supabase: Supabase,
  userId: string,
): Promise<string | null> {
  const { data, error } = await supabase
    .from("membres")
    .select("organisation_id")
    .eq("user_id", userId)
    .eq("role", "admin")
    .order("cree_le", { ascending: true })
    .limit(1)
    .maybeSingle();
  if (error || !data) return null;
  return data.organisation_id as string;
}
