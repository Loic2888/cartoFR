"use server";

// Corrections d'un groupe : enregistrer une version, puis relancer la carto
// (T020, T051, FR-005). Aucune validation : la version enregistrée s'applique.
// La décision est dans lib/reglages/operations.ts et recalcul.ts (testées) ; ici, on
// vérifie la forme de l'appel avec Zod, on identifie l'appelant, et on branche
// la base. Les droits se décident côté serveur, avec la session de
// l'appelant (RLS), jamais d'après ce que le navigateur envoie.
import { z } from "zod";

import { cleEmpreinte } from "@/lib/reglages/cle";
import { depotSupabase } from "@/lib/reglages/depot";
import { MESSAGES, type Resultat, enregistrerVersionAvec } from "@/lib/reglages/operations";
import { relancerApres } from "@/lib/reglages/relancer";
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

const schemaVersion = z.strictObject({
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

export async function enregistrerEtRecalculer(entree: unknown): Promise<Resultat> {
  const { supabase, user } = await utilisateurCourant();
  const saisie = schemaVersion.safeParse(entree);
  if (!saisie.success) return MAL_FORME;
  const groupeId = saisie.data.groupeId;

  let resultat: Resultat;
  try {
    resultat = await enregistrerVersionAvec(
      depotSupabase(supabase, creerClientAdmin),
      user.id,
      saisie.data,
      cleEmpreinte(),
    );
  } catch {
    // Rien de la saisie dans le journal : elle peut contenir un nom de famille.
    console.error("corrections : enregistrement de la version impossible");
    return { statut: "erreur", message: MESSAGES.base };
  }
  return relancerApres(resultat, supabase, creerClientAdmin, groupeId);
}
