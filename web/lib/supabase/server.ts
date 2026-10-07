// Client Supabase côté serveur, lié à la session de l'utilisateur (T009).
// Server Components, Server Actions et Route Handlers. Il agit avec les droits
// de l'utilisateur connecté : RLS filtre tout ce qu'il lit.
import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { COOKIE_SECURISE, NOM_COOKIE_SESSION, configServeur } from "./env";

/** Un client par requête : il lit et écrit les cookies de cette requête. */
export async function creerClientServeur() {
  const magasin = await cookies();
  const { url, cleAnon } = configServeur();
  return createServerClient(url, cleAnon, {
    cookieOptions: { name: NOM_COOKIE_SESSION, secure: COOKIE_SECURISE },
    cookies: {
      getAll: () => magasin.getAll(),
      setAll: (aPoser) => {
        try {
          for (const { name, value, options } of aPoser) {
            magasin.set(name, value, options);
          }
        } catch {
          // Appelé depuis un Server Component, qui ne peut pas poser de cookie :
          // sans effet, proxy.ts rafraîchit la session à chaque requête.
        }
      },
    },
  });
}
