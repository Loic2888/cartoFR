// Export CSV d'une carto (T023, FR-007, SC-005) : le fichier livré au client.
//
// Tout est lu avec la session de l'utilisateur (RLS), jamais avec la clé
// service_role : une carto d'une autre organisation n'existe pas pour lui,
// d'où un 404, sans dire si elle existe ailleurs. Seule une carto terminée
// s'exporte (409 sinon). Le CSV est construit par lib/cartos/csv.ts.
//
// Aucun nom de personne (garde-fou 6) : on n'exporte que les colonnes de
// carto_societes, qui n'a aucune colonne de personne physique (principe 6).
// Aucune ligne du résultat n'est journalisée, seulement des codes d'erreur.
import type { NextRequest } from "next/server";
import { z } from "zod";

import { type SocieteExport, construireCsv, contentDisposition } from "@/lib/cartos/csv";
import { creerClientServeur } from "@/lib/supabase/server";

// Un seul littéral : supabase-js en déduit le type des lignes.
const COLONNES_LUES =
  "siren, nom, niveau, maison_mere_siren, confiance, preuve, ciblable, raison_ciblable, opposition_prospection, non_diffusible";

/** Lecture par pages : PostgREST peut plafonner le nombre de lignes rendues. */
const PAGE = 1000;

const MESSAGES = {
  connexion: "Vous n'êtes pas connecté. Connectez-vous, puis relancez l'export.",
  introuvable: "Cette carto n'existe pas, ou vous n'y avez pas accès.",
  pasTerminee: "Cette carto n'est pas terminée : l'export sera possible quand elle le sera.",
  base: "L'export a échoué. Réessayez dans un instant, et si cela persiste, prévenez l'administrateur.",
} as const;

/** Réponse texte en français, jamais mise en cache. */
function erreur(status: number, message: string): Response {
  return new Response(message, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
  });
}

export async function GET(
  _request: NextRequest,
  ctx: RouteContext<"/groupes/[id]/cartos/[cartoId]/export">,
) {
  const { id, cartoId } = await ctx.params;
  if (!z.uuid().safeParse(id).success || !z.uuid().safeParse(cartoId).success) {
    return erreur(404, MESSAGES.introuvable);
  }

  const supabase = await creerClientServeur();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return erreur(401, MESSAGES.connexion);

  const [{ data: groupe, error: erreurGroupe }, { data: carto, error: erreurCarto }] = await Promise.all([
    supabase.from("groupes").select("nom").eq("id", id).maybeSingle(),
    supabase.from("cartos").select("statut, date_donnees").eq("id", cartoId).eq("groupe_id", id).maybeSingle(),
  ]);
  if (erreurGroupe || erreurCarto) {
    console.error("export : lecture de la carto impossible", {
      code: erreurGroupe?.code ?? erreurCarto?.code,
    });
    return erreur(500, MESSAGES.base);
  }
  if (!groupe || !carto) return erreur(404, MESSAGES.introuvable);
  if (carto.statut !== "terminee") return erreur(409, MESSAGES.pasTerminee);

  const societes: SocieteExport[] = [];
  for (let debut = 0; ; debut += PAGE) {
    const { data, error } = await supabase
      .from("carto_societes")
      .select(COLONNES_LUES)
      .eq("carto_id", cartoId)
      .order("siren", { ascending: true })
      .range(debut, debut + PAGE - 1);
    if (error) {
      console.error("export : lecture des sociétés impossible", { code: error.code });
      return erreur(500, MESSAGES.base);
    }
    societes.push(...(data as SocieteExport[]));
    if (data.length < PAGE) break;
  }

  const dateDonnees = carto.date_donnees as string | null;
  return new Response(construireCsv(societes, dateDonnees), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": contentDisposition(groupe.nom as string, dateDonnees),
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
