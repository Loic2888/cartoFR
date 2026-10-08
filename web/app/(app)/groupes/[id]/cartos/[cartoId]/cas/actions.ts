"use server";

// Décider d'un cas douteux (T028, FR-009). La logique est dans
// lib/cartos/cas.ts (testée) ; ici, on vérifie la forme de l'appel avec Zod,
// on identifie l'appelant, et on branche la base.
//
// Le cas et sa carto sont lus avec la session de l'appelant (RLS) : c'est ce
// qui décide du droit d'écrire. La décision est écrite avec la clé
// service_role (aucune politique d'écriture pour authenticated, migration
// 0003), seulement après cette lecture, avec l'organisation et le groupe lus,
// l'auteur connecté ; la date est posée par la base.
import { revalidatePath } from "next/cache";
import { z } from "zod";

import { DECISIONS, type DepotCas, MESSAGES, type Resultat, deciderAvec } from "@/lib/cartos/cas";
import { utilisateurCourant } from "@/lib/session";
import { creerClientAdmin } from "@/lib/supabase/admin";

const schemaDecision = z.strictObject({
  groupeId: z.uuid(),
  cartoId: z.uuid(),
  siren: z.string().regex(/^[0-9]{9}$/),
  decision: z.enum(DECISIONS),
});

type ClientUtilisateur = Awaited<ReturnType<typeof utilisateurCourant>>["supabase"];

function depotSupabase(utilisateur: ClientUtilisateur): DepotCas {
  return {
    async lireCas(groupeId, cartoId, siren) {
      const [{ data: carto, error: erreurCarto }, { data: cas, error: erreurCas }] = await Promise.all([
        utilisateur
          .from("cartos")
          .select("groupe_id, organisation_id")
          .eq("id", cartoId)
          .eq("groupe_id", groupeId)
          .maybeSingle(),
        utilisateur
          .from("carto_cas")
          .select("organisation_id")
          .eq("carto_id", cartoId)
          .eq("siren", siren)
          .maybeSingle(),
      ]);
      const erreur = erreurCarto ?? erreurCas;
      if (erreur) console.error("cas : lecture du cas impossible", { code: erreur.code });
      if (erreur || !carto || !cas || cas.organisation_id !== carto.organisation_id) return null;
      return { organisationId: carto.organisation_id as string, groupeId: carto.groupe_id as string };
    },

    async insererDecision(ligne) {
      const { data, error } = await creerClientAdmin()
        .from("decisions")
        .insert({
          organisation_id: ligne.organisationId,
          groupe_id: ligne.groupeId,
          carto_id: ligne.cartoId,
          siren: ligne.siren,
          decision: ligne.decision,
          decide_par: ligne.auteur,
        })
        .select("decide_le")
        .single();
      if (error || !data) {
        console.error("cas : insertion de la décision impossible", { code: error?.code });
        return "erreur";
      }
      return { decideLe: data.decide_le as string };
    },
  };
}

export async function deciderCas(entree: unknown): Promise<Resultat> {
  const { supabase, user } = await utilisateurCourant();
  const demande = schemaDecision.safeParse(entree);
  if (!demande.success) return { statut: "erreur", message: MESSAGES.introuvable };

  try {
    const resultat = await deciderAvec(depotSupabase(supabase), user.id, demande.data);
    if (resultat.statut === "ok") {
      revalidatePath(`/groupes/${demande.data.groupeId}/cartos/${demande.data.cartoId}/cas`);
    }
    return resultat;
  } catch {
    console.error("cas : décision impossible");
    return { statut: "erreur", message: MESSAGES.base };
  }
}
