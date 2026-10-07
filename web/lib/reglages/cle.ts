// Clé d'empreinte des familles exclues (T020). Serveur seulement : la clé ne
// doit jamais atteindre le navigateur.
import "server-only";

export const VARIABLE_CLE = "CARTOFR_CLE_EMPREINTE";

/** La clé, ou null si elle n'est pas définie (l'action rend alors un refus en
 * français au lieu d'enregistrer un nom ou une empreinte vide). */
export function cleEmpreinte(): string | null {
  return process.env[VARIABLE_CLE] || null;
}
