// « Enregistrer et recalculer » (T051, US8) : une version des corrections
// enregistrée relance aussitôt la carto du groupe, sans étape de validation.
//
// Règles :
// - rien n'est lancé si l'enregistrement a échoué ;
// - la version enregistrée le reste même si le lancement échoue (une carto déjà
//   en cours, la file indisponible) : le message dit les deux choses, et la
//   carto se relance plus tard depuis la page du groupe ;
// - le lancement est celui de la page du groupe (lib/cartos/operations.ts),
//   avec ses propres garde-fous : groupe lu sous RLS, une seule carto active.
import type { Resultat as ResultatLancement } from "@/lib/cartos/operations";

export const MESSAGES_RECALCUL = {
  relancee: "La carto est relancée avec ces corrections : elle apparaît sur la page du groupe.",
  nonRelancee: "La carto n'a pas été relancée :",
  echecLancement:
    "le lancement a échoué. Relancez-la depuis la page du groupe ; si cela persiste, prévenez l'administrateur.",
} as const;

export async function puisRecalculer<R extends { statut: "ok"; message: string } | { statut: "erreur"; message: string }>(
  enregistrement: R,
  lancer: () => Promise<ResultatLancement>,
): Promise<R> {
  if (enregistrement.statut !== "ok") return enregistrement;
  let lancement: ResultatLancement;
  try {
    lancement = await lancer();
  } catch (erreur) {
    // Le nom de la classe seulement : jamais le message, qui pourrait citer une valeur.
    console.error("corrections : relance de la carto impossible", {
      erreur: erreur instanceof Error ? erreur.name : typeof erreur,
    });
    lancement = { statut: "erreur", message: MESSAGES_RECALCUL.echecLancement };
  }
  const suite =
    lancement.statut === "ok"
      ? MESSAGES_RECALCUL.relancee
      : `${MESSAGES_RECALCUL.nonRelancee} ${minusculeInitiale(lancement.message)}`;
  return { ...enregistrement, message: `${enregistrement.message} ${suite}` };
}

function minusculeInitiale(texte: string): string {
  return texte.charAt(0).toLocaleLowerCase("fr-FR") + texte.slice(1);
}
