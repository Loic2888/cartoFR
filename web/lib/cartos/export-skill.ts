// Export d'une carto au format du skill account-mapping (T029, FR-010) : un
// zip de 6 tables CSV, à importer dans HubSpot ou Cargo. Aucune poussée vers
// un outil tiers : le fichier est rendu à l'utilisateur, l'import est le sien.
//
// Les tables sont construites par le worker (cartofr.exports.skill), derrière
// la route interne GET /export/skill/<carto>?organisation=<uuid> du service
// recherche (RECHERCHE_URL, réseau Docker seulement). Aucune règle du moteur
// ici (principe 7) : on contrôle l'accès, on relaie, on nomme le fichier.
//
// Cloisonnement (règle produit 7) : le groupe et la carto sont lus avec la
// session de l'utilisateur (RLS), jamais avec la clé service_role. Une carto
// d'une autre organisation n'existe pas pour lui : 404, sans dire si elle
// existe ailleurs, et le worker n'est pas appelé. L'organisation passée au
// worker est celle de la ligne lue sous RLS, jamais une saisie ; le worker
// filtre la carto par elle (défense en profondeur).
//
// Aucun nom de personne (garde-fou 6) : les tables n'ont aucune colonne de
// personne (testé dans worker/tests/exports/test_skill.py). Rien du contenu
// n'est journalisé, seulement des codes d'erreur.
import "server-only";

import type { SupabaseClient } from "@supabase/supabase-js";
import { z } from "zod";

import { contentDisposition } from "./csv";

export const MESSAGES_EXPORT_SKILL = {
  connexion: "Vous n'êtes pas connecté. Connectez-vous, puis relancez l'export.",
  introuvable: "Cette carto n'existe pas, ou vous n'y avez pas accès.",
  pasTerminee: "Cette carto n'est pas terminée : l'export sera possible quand elle le sera.",
  indisponible:
    "Le service d'export est momentanément indisponible. Réessayez dans quelques minutes ; si cela persiste, prévenez l'administrateur.",
  base: "L'export a échoué. Réessayez dans un instant, et si cela persiste, prévenez l'administrateur.",
} as const;

/** Fin du nom de fichier : `cartofr-<groupe>-<date>-hubspot-cargo.zip`. */
export const FIN_FICHIER = "-hubspot-cargo.zip";

// Une carto de VINCI (un millier de sociétés) se lit et se zippe en moins d'une seconde.
const DELAI_MS = 60_000;

type Options = {
  /** Remplace fetch (tests). */
  fetch?: typeof fetch;
  /** Remplace RECHERCHE_URL (tests). */
  url?: string;
  delaiMs?: number;
};

/** Réponse texte en français, jamais mise en cache. */
function erreur(status: number, message: string): Response {
  return new Response(message, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
  });
}

/** Message et statut HTTP rendus pour une réponse en erreur du worker. */
export function erreurWorker(statut: number): Response {
  if (statut === 404) return erreur(404, MESSAGES_EXPORT_SKILL.introuvable);
  if (statut === 409) return erreur(409, MESSAGES_EXPORT_SKILL.pasTerminee);
  if (statut === 503) return erreur(503, MESSAGES_EXPORT_SKILL.indisponible);
  return erreur(502, MESSAGES_EXPORT_SKILL.base);
}

/** L'export du skill d'une carto, pour l'utilisateur de cette session. */
export async function exporterSkill(
  supabase: SupabaseClient,
  groupeId: string,
  cartoId: string,
  options: Options = {},
): Promise<Response> {
  if (!z.uuid().safeParse(groupeId).success || !z.uuid().safeParse(cartoId).success) {
    return erreur(404, MESSAGES_EXPORT_SKILL.introuvable);
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return erreur(401, MESSAGES_EXPORT_SKILL.connexion);

  const [{ data: groupe, error: erreurGroupe }, { data: carto, error: erreurCarto }] = await Promise.all([
    supabase.from("groupes").select("nom").eq("id", groupeId).maybeSingle(),
    supabase
      .from("cartos")
      .select("statut, date_donnees, organisation_id")
      .eq("id", cartoId)
      .eq("groupe_id", groupeId)
      .maybeSingle(),
  ]);
  if (erreurGroupe || erreurCarto) {
    console.error("export skill : lecture de la carto impossible", {
      code: erreurGroupe?.code ?? erreurCarto?.code,
    });
    return erreur(500, MESSAGES_EXPORT_SKILL.base);
  }
  if (!groupe || !carto) return erreur(404, MESSAGES_EXPORT_SKILL.introuvable);
  if (carto.statut !== "terminee") return erreur(409, MESSAGES_EXPORT_SKILL.pasTerminee);
  const organisation = String(carto.organisation_id);
  if (!z.uuid().safeParse(organisation).success) return erreur(500, MESSAGES_EXPORT_SKILL.base);

  const base = options.url ?? process.env.RECHERCHE_URL;
  if (!base) {
    console.error("export skill : variable d'environnement manquante : RECHERCHE_URL");
    return erreur(503, MESSAGES_EXPORT_SKILL.indisponible);
  }
  // Hôte et chemin fixes ; les deux identifiants sont des UUID vérifiés (pas de SSRF).
  const url = new URL(`/export/skill/${cartoId}`, base);
  url.searchParams.set("organisation", organisation);

  let r: Response;
  try {
    r = await (options.fetch ?? fetch)(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(options.delaiMs ?? DELAI_MS),
    });
  } catch (e) {
    console.error("export skill : service injoignable", { erreur: (e as Error)?.name });
    return erreur(503, MESSAGES_EXPORT_SKILL.indisponible);
  }
  if (!r.ok) {
    console.error("export skill : réponse en erreur", { statut: r.status });
    return erreurWorker(r.status);
  }
  if (!(r.headers.get("Content-Type") ?? "").startsWith("application/zip")) {
    console.error("export skill : réponse inattendue", { statut: r.status });
    return erreur(502, MESSAGES_EXPORT_SKILL.base);
  }

  const dateDonnees = carto.date_donnees as string | null;
  return new Response(await r.arrayBuffer(), {
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition": contentDisposition(groupe.nom as string, dateDonnees, FIN_FICHIER),
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
