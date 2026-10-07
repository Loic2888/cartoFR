"use server";

// Réglages d'un groupe : enregistrer un brouillon, valider une version (T020,
// FR-005). La décision est dans lib/reglages/operations.ts (testée) ; ici, on
// vérifie la forme de l'appel avec Zod, on identifie l'appelant, et on branche
// la base. Les droits se décident côté serveur, avec la session de
// l'appelant (RLS), jamais d'après ce que le navigateur envoie.
import { revalidatePath } from "next/cache";
import { z } from "zod";

import { cleEmpreinte } from "@/lib/reglages/cle";
import { depotSupabase } from "@/lib/reglages/depot";
import {
  MESSAGES,
  type Resultat,
  enregistrerBrouillonAvec,
  validerAvec,
} from "@/lib/reglages/operations";
import { LISTES } from "@/lib/reglages/schema";
import { utilisateurCourant } from "@/lib/session";
import { creerClientAdmin } from "@/lib/supabase/admin";

const MAL_FORME: Resultat = {
  statut: "erreur",
  message: "La demande est incomplète. Rechargez la page, puis réessayez.",
};

// Un champ de liste : du texte, une valeur par ligne. Borné pour qu'une
// requête énorme ne passe pas jusqu'à la base.
const champListe = z.string().max(200_000);

const schemaBrouillon = z.strictObject({
  groupeId: z.uuid(),
  baseVersion: z.int().min(0),
  listes: z.strictObject(
    Object.fromEntries(LISTES.map((l) => [l.cle, champListe])) as Record<
      (typeof LISTES)[number]["cle"],
      typeof champListe
    >,
  ),
  famillesAjoutees: z.string().max(10_000),
  retirerFamilles: z.boolean(),
});

const schemaValidation = z.strictObject({
  groupeId: z.uuid(),
  version: z.int().min(1),
});

export async function enregistrerBrouillon(entree: unknown): Promise<Resultat> {
  const { supabase, user } = await utilisateurCourant();
  const saisie = schemaBrouillon.safeParse(entree);
  if (!saisie.success) return MAL_FORME;

  try {
    const resultat = await enregistrerBrouillonAvec(
      depotSupabase(supabase, creerClientAdmin),
      user.id,
      saisie.data,
      cleEmpreinte(),
    );
    if (resultat.statut === "ok") revalidatePath(`/groupes/${saisie.data.groupeId}/reglages`);
    return resultat;
  } catch {
    // Rien de la saisie dans le journal : elle peut contenir un nom de famille.
    console.error("réglages : enregistrement du brouillon impossible");
    return { statut: "erreur", message: MESSAGES.base };
  }
}

export async function validerVersion(entree: unknown): Promise<Resultat> {
  const { supabase, user } = await utilisateurCourant();
  const demande = schemaValidation.safeParse(entree);
  if (!demande.success) return MAL_FORME;

  try {
    const resultat = await validerAvec(depotSupabase(supabase, creerClientAdmin), user.id, demande.data);
    if (resultat.statut === "ok") revalidatePath(`/groupes/${demande.data.groupeId}/reglages`);
    return resultat;
  } catch {
    console.error("réglages : validation impossible");
    return { statut: "erreur", message: MESSAGES.base };
  }
}
