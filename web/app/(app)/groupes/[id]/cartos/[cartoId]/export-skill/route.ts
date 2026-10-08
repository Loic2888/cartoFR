// Export d'une carto pour HubSpot ou Cargo (T029, FR-010) : les 6 tables du
// skill account-mapping dans un zip. Contrôle d'accès et relais au worker dans
// lib/cartos/export-skill.ts : lecture avec la session de l'utilisateur (RLS),
// 404 pour une carto d'une autre organisation, 409 si elle n'est pas terminée.
import type { NextRequest } from "next/server";

import { exporterSkill } from "@/lib/cartos/export-skill";
import { creerClientServeur } from "@/lib/supabase/server";

export async function GET(
  _request: NextRequest,
  ctx: RouteContext<"/groupes/[id]/cartos/[cartoId]/export-skill">,
) {
  const { id, cartoId } = await ctx.params;
  return exporterSkill(await creerClientServeur(), id, cartoId);
}
