// Le dépôt des corrections sur Supabase (T020, T051), branché par reglages/actions.ts.
//
// Lectures avec la session de l'utilisateur : RLS limite aux groupes de ses
// organisations, c'est là que se décide le droit d'écrire. Écritures avec la
// clé service_role (aucune politique d'écriture pour authenticated,
// migration 0002), seulement après cette lecture.
import "server-only";

import type { creerClientAdmin } from "@/lib/supabase/admin";
import type { creerClientServeur } from "@/lib/supabase/server";

import type { Depot } from "./operations";
import type { Reglages } from "./schema";

type ClientUtilisateur = Awaited<ReturnType<typeof creerClientServeur>>;
type ClientAdmin = ReturnType<typeof creerClientAdmin>;

/** Violation d'unicité Postgres : (groupe_id, version) déjà pris. */
const UNICITE = "23505";

export function depotSupabase(
  utilisateur: ClientUtilisateur,
  admin: () => ClientAdmin,
): Depot {
  return {
    async lireGroupe(groupeId) {
      const { data, error } = await utilisateur
        .from("groupes")
        .select("id, organisation_id, tete_siren, nom")
        .eq("id", groupeId)
        .maybeSingle();
      if (error) console.error("réglages : lecture du groupe impossible", { code: error.code });
      if (error || !data) return null;
      return {
        id: data.id as string,
        organisationId: data.organisation_id as string,
        teteSiren: data.tete_siren as string,
        nom: data.nom as string,
      };
    },

    async derniereVersion(groupeId) {
      return lireVersion(utilisateur, groupeId, false);
    },

    async derniereEnregistree(groupeId) {
      return lireVersion(utilisateur, groupeId, true);
    },

    async insererVersion(ligne) {
      const { error } = await admin().from("reglages").insert({
        groupe_id: ligne.groupeId,
        organisation_id: ligne.organisationId,
        version: ligne.version,
        contenu: ligne.contenu,
        origine: "saisie",
        cree_par: ligne.creePar,
      });
      if (!error) return "ok";
      if (error.code === UNICITE) return "conflit";
      // Le code seulement : jamais le contenu, qui peut porter un nom saisi.
      console.error("réglages : insertion d'une version impossible", { code: error.code });
      return "erreur";
    },
  };
}

/** La version de numéro le plus haut, lue sous RLS ; `enregistree` : hors propositions de l'IA. */
async function lireVersion(utilisateur: ClientUtilisateur, groupeId: string, enregistree: boolean) {
  let requete = utilisateur.from("reglages").select("version, origine, contenu").eq("groupe_id", groupeId);
  if (enregistree) requete = requete.neq("origine", "proposition");
  const { data, error } = await requete.order("version", { ascending: false }).limit(1).maybeSingle();
  if (error) {
    console.error("réglages : lecture de la dernière version impossible", { code: error.code });
    throw new Error("lecture des réglages impossible");
  }
  if (!data) return null;
  return { version: data.version as number, origine: data.origine as string, contenu: data.contenu as Reglages };
}
