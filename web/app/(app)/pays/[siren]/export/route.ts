// Export CSV de la carto d'une société dans la carto du pays (T050, C5) : les
// mêmes colonnes que l'export d'une carto (T023), construites par
// lib/cartos/csv.ts, avec la date des données sur chaque ligne.
//
// Réservé aux utilisateurs connectés (401 sinon). La carto du pays est
// commune à toutes les organisations : rien à cloisonner ici. Aucun nom de
// personne (garde-fou 6) : les lignes viennent de la route `/groupe`, relue par
// Zod, qui n'a aucun champ de personne. Aucune ligne n'est journalisée.
import type { NextRequest } from "next/server";

import { construireCsv, contentDisposition } from "@/lib/cartos/csv";
import { lignesExport, lireCartoPays } from "@/lib/pays";
import { creerClientServeur } from "@/lib/supabase/server";

const CONNEXION = "Vous n'êtes pas connecté. Connectez-vous, puis relancez l'export.";

/** Réponse texte en français, jamais mise en cache. */
function erreur(status: number, message: string): Response {
  return new Response(message, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
  });
}

export async function GET(_request: NextRequest, ctx: RouteContext<"/pays/[siren]/export">) {
  const { siren } = await ctx.params;

  const supabase = await creerClientServeur();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return erreur(401, CONNEXION);

  const resultat = await lireCartoPays(siren);
  if (!resultat.ok) return erreur(resultat.introuvable ? 404 : resultat.status, resultat.message);

  const { carto } = resultat;
  return new Response(construireCsv(lignesExport(carto), carto.date_donnees), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": contentDisposition(carto.nom ?? carto.siren, carto.date_donnees),
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
