// Réglages Supabase lus à l'exécution, jamais au build (T009).
//
// Aucune variable NEXT_PUBLIC_ : Next les fige dans le bundle au moment du
// build, il faudrait alors une image par environnement. Le serveur lit ses
// variables au démarrage du conteneur (infra/docker-compose.yml) et passe au
// navigateur, s'il en a besoin, la seule partie publique : configPublique().

/** Nom commun du cookie de session, côté serveur et navigateur. Sans lui,
 * @supabase/ssr le déduit de l'URL : `kong` côté serveur, le domaine côté
 * navigateur, et les deux ne se verraient pas. */
export const NOM_COOKIE_SESSION = "sb-cartofr-auth-token";

/** Lit une variable obligatoire. Le message nomme la variable, jamais sa valeur. */
export function lireEnv(nom: string): string {
  const valeur = process.env[nom];
  if (!valeur) {
    throw new Error(`Variable d'environnement manquante : ${nom}`);
  }
  return valeur;
}

/** URL interne de Supabase (kong) et clé anon, pour les clients côté serveur. */
export function configServeur() {
  return { url: lireEnv("SUPABASE_URL"), cleAnon: lireEnv("SUPABASE_ANON_KEY") };
}

/** Ce que le navigateur peut connaître : l'URL publique et la clé anon,
 * publique par nature (RLS fait le cloisonnement). À passer en props depuis
 * un Server Component vers lib/supabase/client.ts. */
export function configPublique() {
  return { url: lireEnv("SUPABASE_PUBLIC_URL"), cleAnon: lireEnv("SUPABASE_ANON_KEY") };
}

/** Cookie de session en `Secure` hors développement local (servi en HTTPS par Caddy). */
export const COOKIE_SECURISE = process.env.NODE_ENV === "production";
