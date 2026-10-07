// Le dépôt des cartos sur Supabase (T021), branché par cartos/actions.ts.
//
// Lectures du groupe et des réglages avec la session de l'utilisateur : RLS
// limite aux groupes de ses organisations, c'est ce qui décide du droit de
// lancer. Écritures avec la clé service_role (aucune politique d'écriture
// pour authenticated, migration 0002), seulement après cette lecture, et
// toujours avec l'organisation du groupe lu.
import "server-only";

import type { creerClientAdmin } from "@/lib/supabase/admin";
import type { creerClientServeur } from "@/lib/supabase/server";

import { bloquante } from "./affichage";
import type { Depot } from "./operations";

type ClientUtilisateur = Awaited<ReturnType<typeof creerClientServeur>>;
type ClientAdmin = ReturnType<typeof creerClientAdmin>;

export function depotSupabase(utilisateur: ClientUtilisateur, admin: () => ClientAdmin): Depot {
  return {
    async lireGroupe(groupeId) {
      const { data, error } = await utilisateur
        .from("groupes")
        .select("id, organisation_id")
        .eq("id", groupeId)
        .maybeSingle();
      if (error) console.error("cartos : lecture du groupe impossible", { code: error.code });
      if (error || !data) return null;
      return { id: data.id as string, organisationId: data.organisation_id as string };
    },

    async derniereVersionValidee(groupeId) {
      const { data, error } = await utilisateur
        .from("reglages")
        .select("id, version")
        .eq("groupe_id", groupeId)
        .not("valide_le", "is", null)
        .order("version", { ascending: false })
        .limit(1)
        .maybeSingle();
      if (error) {
        console.error("cartos : lecture des réglages impossible", { code: error.code });
        throw new Error("lecture des réglages impossible");
      }
      return data ? { id: data.id as string, version: data.version as number } : null;
    },

    async cartosActives(groupeId) {
      // service_role : voit aussi une carto qu'un autre membre vient d'insérer.
      const { data, error } = await admin()
        .from("cartos")
        .select("id, travail_id, statut, cree_le")
        .eq("groupe_id", groupeId)
        .in("statut", ["en_attente", "en_cours"]);
      if (error) {
        console.error("cartos : lecture des cartos actives impossible", { code: error.code });
        throw new Error("lecture des cartos impossible");
      }
      const maintenant = Date.now();
      return (data ?? [])
        .filter((c) =>
          bloquante(
            {
              statut: c.statut as string,
              travail_id: c.travail_id as number | null,
              cree_le: c.cree_le as string,
            },
            maintenant,
          ),
        )
        .map((c) => c.id as string);
    },

    async insererCarto(ligne) {
      const { data, error } = await admin()
        .from("cartos")
        .insert({
          organisation_id: ligne.organisationId,
          groupe_id: ligne.groupeId,
          reglages_id: ligne.reglagesId,
          statut: "en_attente",
        })
        .select("id")
        .single();
      if (error || !data) {
        console.error("cartos : insertion de la carto impossible", { code: error?.code });
        return "erreur";
      }
      return data.id as string;
    },

    async supprimerCarto(cartoId) {
      const { error } = await admin().from("cartos").delete().eq("id", cartoId).eq("statut", "en_attente");
      if (error) console.error("cartos : suppression de la carto impossible", { code: error.code });
    },

    async insererTravail(ligne) {
      const { data, error } = await admin()
        .from("travaux")
        .insert({
          type: "carto",
          organisation_id: ligne.organisationId,
          parametres: { carto_id: ligne.cartoId },
        })
        .select("id")
        .single();
      if (error || !data) {
        console.error("cartos : insertion du travail impossible", { code: error?.code });
        return "erreur";
      }
      return Number(data.id);
    },

    async lierTravail(cartoId, travailId) {
      const { error } = await admin()
        .from("cartos")
        .update({ travail_id: travailId })
        .eq("id", cartoId)
        .is("travail_id", null);
      if (error) console.error("cartos : lien carto → travail impossible", { code: error.code });
      return !error;
    },
  };
}
