// Le dépôt des réglages sur Supabase (T020), branché par reglages/actions.ts.
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
      const { data, error } = await utilisateur
        .from("reglages")
        .select("id, version, contenu, valide_le")
        .eq("groupe_id", groupeId)
        .order("version", { ascending: false })
        .limit(1)
        .maybeSingle();
      if (error) {
        console.error("réglages : lecture de la dernière version impossible", { code: error.code });
        throw new Error("lecture des réglages impossible");
      }
      if (!data) return null;
      return {
        id: data.id as string,
        version: data.version as number,
        contenu: data.contenu as Reglages,
        valideLe: (data.valide_le as string | null) ?? null,
      };
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

    async marquerValidee(versionId, validePar, valideLe) {
      const { data, error } = await admin()
        .from("reglages")
        .update({ valide_le: valideLe, valide_par: validePar })
        .eq("id", versionId)
        .is("valide_le", null)
        .select("id");
      if (error) {
        console.error("réglages : validation impossible", { code: error.code });
        return "erreur";
      }
      return (data ?? []).length > 0;
    },
  };
}
