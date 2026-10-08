// Le dépôt de la proposition IA sur Supabase (T026), branché par
// reglages/actions-proposition.ts.
//
// Comme depot.ts : lectures avec la session de l'utilisateur (RLS, c'est là
// que se décide le droit d'écrire), écritures avec la clé service_role, après
// cette lecture seulement.
import "server-only";

import type { creerClientAdmin } from "@/lib/supabase/admin";
import type { creerClientServeur } from "@/lib/supabase/server";

import type { DepotProposition, TravailProposition } from "./proposition";
import type { Reglages } from "./schema";

type ClientUtilisateur = Awaited<ReturnType<typeof creerClientServeur>>;
type ClientAdmin = ReturnType<typeof creerClientAdmin>;

/** Violation d'unicité Postgres : (groupe_id, version) déjà pris. */
const UNICITE = "23505";

export function depotProposition(utilisateur: ClientUtilisateur, admin: () => ClientAdmin): DepotProposition {
  return {
    async lireGroupe(groupeId) {
      const { data, error } = await utilisateur
        .from("groupes")
        .select("id, organisation_id, tete_siren, nom")
        .eq("id", groupeId)
        .maybeSingle();
      if (error) console.error("proposition : lecture du groupe impossible", { code: error.code });
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
        .select("id, version, origine, contenu, proposition, valide_le")
        .eq("groupe_id", groupeId)
        .order("version", { ascending: false })
        .limit(1)
        .maybeSingle();
      if (error) {
        console.error("proposition : lecture de la dernière version impossible", { code: error.code });
        throw new Error("lecture des réglages impossible");
      }
      if (!data) return null;
      return {
        id: data.id as string,
        version: data.version as number,
        origine: data.origine as string,
        contenu: data.contenu as Reglages,
        proposition: data.proposition as unknown,
        valideLe: (data.valide_le as string | null) ?? null,
      };
    },

    async dernierTravail(groupeId) {
      return lireDernierTravail(utilisateur, groupeId);
    },

    async insererTravail(ligne) {
      const { error } = await admin()
        .from("travaux")
        .insert({
          type: "proposition",
          organisation_id: ligne.organisationId,
          parametres: { groupe_id: ligne.groupeId, demande_par: ligne.demandePar },
        });
      if (!error) return "ok";
      console.error("proposition : insertion du travail impossible", { code: error.code });
      return "erreur";
    },

    async insererVersionValidee(ligne) {
      const { error } = await admin().from("reglages").insert({
        groupe_id: ligne.groupeId,
        organisation_id: ligne.organisationId,
        version: ligne.version,
        contenu: ligne.contenu,
        origine: "saisie",
        proposition_id: ligne.propositionId,
        corrections: ligne.corrections,
        cree_par: ligne.par,
        valide_le: ligne.le,
        valide_par: ligne.par,
      });
      if (!error) return "ok";
      if (error.code === UNICITE) return "conflit";
      // Le code seulement : jamais le contenu.
      console.error("proposition : insertion de la version validée impossible", { code: error.code });
      return "erreur";
    },
  };
}

/** Le dernier travail `proposition` du groupe, lu sous RLS (travaux de ses organisations). */
export async function lireDernierTravail(
  utilisateur: ClientUtilisateur,
  groupeId: string,
): Promise<TravailProposition | null> {
  const { data, error } = await utilisateur
    .from("travaux")
    .select("statut, erreur, cree_le")
    .eq("type", "proposition")
    .eq("parametres->>groupe_id", groupeId)
    .order("cree_le", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) {
    console.error("proposition : lecture du travail impossible", { code: error.code });
    return null;
  }
  if (!data) return null;
  return {
    statut: data.statut as TravailProposition["statut"],
    erreur: (data.erreur as string | null) ?? null,
    creeLe: data.cree_le as string,
  };
}
