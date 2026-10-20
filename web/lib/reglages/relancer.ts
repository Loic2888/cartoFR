// Après l'enregistrement d'une version des corrections, relancer la carto du groupe et
// rafraîchir ses pages (T051). Commun aux deux façons d'enregistrer : l'éditeur et la revue
// d'une proposition de l'IA (reglages/actions.ts, actions-proposition.ts).
import "server-only";

import { revalidatePath } from "next/cache";

import { depotSupabase as depotCartos } from "@/lib/cartos/depot";
import { lancerCartoAvec } from "@/lib/cartos/operations";
import type { creerClientAdmin } from "@/lib/supabase/admin";
import type { creerClientServeur } from "@/lib/supabase/server";

import { puisRecalculer } from "./recalcul";

type ClientUtilisateur = Awaited<ReturnType<typeof creerClientServeur>>;
type ClientAdmin = ReturnType<typeof creerClientAdmin>;

export async function relancerApres<R extends { statut: "ok"; message: string } | { statut: "erreur"; message: string }>(
  resultat: R,
  utilisateur: ClientUtilisateur,
  admin: () => ClientAdmin,
  groupeId: string,
): Promise<R> {
  const final = await puisRecalculer(resultat, () => lancerCartoAvec(depotCartos(utilisateur, admin), groupeId));
  if (final.statut === "ok") {
    revalidatePath(`/groupes/${groupeId}/reglages`);
    revalidatePath(`/groupes/${groupeId}`);
  }
  return final;
}
