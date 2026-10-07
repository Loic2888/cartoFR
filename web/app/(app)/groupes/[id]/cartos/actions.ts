"use server";

// Lancer une carto (T021, FR-005). La décision est dans lib/cartos/operations.ts
// (testée) ; ici, on vérifie la forme de l'appel avec Zod, on identifie
// l'appelant, et on branche la base. Le droit de lancer se décide avec la
// session de l'appelant (RLS : le groupe doit être de son organisation),
// jamais d'après ce que le navigateur envoie.
import { revalidatePath } from "next/cache";
import { z } from "zod";

import { MESSAGES } from "@/lib/cartos/affichage";
import { depotSupabase } from "@/lib/cartos/depot";
import { type Resultat, lancerCartoAvec } from "@/lib/cartos/operations";
import { utilisateurCourant } from "@/lib/session";
import { creerClientAdmin } from "@/lib/supabase/admin";

const schemaLancement = z.strictObject({ groupeId: z.uuid() });

export async function lancerCarto(entree: unknown): Promise<Resultat> {
  const { supabase } = await utilisateurCourant();
  const demande = schemaLancement.safeParse(entree);
  if (!demande.success) return { statut: "erreur", message: MESSAGES.groupeIntrouvable };

  try {
    const resultat = await lancerCartoAvec(depotSupabase(supabase, creerClientAdmin), demande.data.groupeId);
    revalidatePath(`/groupes/${demande.data.groupeId}`);
    return resultat;
  } catch {
    console.error("cartos : lancement impossible");
    return { statut: "erreur", message: MESSAGES.base };
  }
}
