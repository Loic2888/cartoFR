// Client Supabase côté navigateur (T009). Rien ne s'en sert encore : la
// connexion, l'invitation et la déconnexion passent par le serveur.
//
// Pas de variable NEXT_PUBLIC_ (figée au build) : l'URL publique et la clé
// anon viennent du serveur, par configPublique() passée en props.
import { createBrowserClient } from "@supabase/ssr";

import { NOM_COOKIE_SESSION } from "./env";

export function creerClientNavigateur(config: { url: string; cleAnon: string }) {
  return createBrowserClient(config.url, config.cleAnon, {
    cookieOptions: {
      name: NOM_COOKIE_SESSION,
      secure: window.location.protocol === "https:",
    },
  });
}
