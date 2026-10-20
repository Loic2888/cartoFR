"use server";

// Proposition des réglages par l'IA : la demander, enregistrer la revue puis
// relancer la carto (T026, T051, FR-008, SC-007). La logique est dans lib/reglages/proposition.ts (testée) ;
// ici, Zod vérifie la forme de l'appel, on identifie l'appelant et on branche
// la base. Next met en file et enregistre ce que l'humain a choisi ; il ne
// décide rien sur le groupe (principe 7).
import { revalidatePath } from "next/cache";
import { z } from "zod";

import { depotProposition } from "@/lib/reglages/depot-proposition";
import { MESSAGES, type Resultat } from "@/lib/reglages/operations";
import {
  LISTES_PROPOSEES,
  demanderPropositionAvec,
  enregistrerPropositionAvec,
} from "@/lib/reglages/proposition";
import { relancerApres } from "@/lib/reglages/relancer";
import { utilisateurCourant } from "@/lib/session";
import { creerClientAdmin } from "@/lib/supabase/admin";

const MAL_FORME: Resultat = {
  statut: "erreur",
  message: "La demande est incomplète. Rechargez la page, puis réessayez.",
};

const liste = z.enum(LISTES_PROPOSEES);
const valeur = z.string().max(2_000);

const schemaDemande = z.strictObject({ groupeId: z.uuid() });

const schemaRevue = z.strictObject({
  groupeId: z.uuid(),
  version: z.int().min(1),
  decisions: z
    .array(
      z.discriminatedUnion("choix", [
        z.strictObject({ choix: z.literal("accepter") }),
        z.strictObject({ choix: z.literal("rejeter") }),
        z.strictObject({ choix: z.literal("corriger"), valeur, liste }),
      ]),
    )
    .max(5_000),
  ajouts: z.array(z.strictObject({ liste, valeur: z.string().max(200_000) })).max(LISTES_PROPOSEES.length * 50),
});

export async function demanderProposition(entree: unknown): Promise<Resultat> {
  const { supabase, user } = await utilisateurCourant();
  const demande = schemaDemande.safeParse(entree);
  if (!demande.success) return MAL_FORME;
  try {
    const resultat = await demanderPropositionAvec(
      depotProposition(supabase, creerClientAdmin),
      user.id,
      demande.data.groupeId,
    );
    if (resultat.statut === "ok") revalidatePath(`/groupes/${demande.data.groupeId}/reglages`);
    return resultat;
  } catch {
    console.error("proposition : demande impossible");
    return { statut: "erreur", message: MESSAGES.base };
  }
}

export async function enregistrerProposition(entree: unknown): Promise<Resultat> {
  const { supabase, user } = await utilisateurCourant();
  const revue = schemaRevue.safeParse(entree);
  if (!revue.success) return MAL_FORME;
  const groupeId = revue.data.groupeId;

  let resultat: Resultat;
  try {
    resultat = await enregistrerPropositionAvec(depotProposition(supabase, creerClientAdmin), user.id, revue.data);
  } catch {
    console.error("proposition : enregistrement de la revue impossible");
    return { statut: "erreur", message: MESSAGES.base };
  }
  return relancerApres(resultat, supabase, creerClientAdmin, groupeId);
}
