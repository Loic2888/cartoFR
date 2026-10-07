// Garde des pages (T009, C1) : rafraîchit la session Supabase à chaque
// requête et renvoie vers /connexion toute page demandée sans session.
// (Next.js 16 : `proxy.ts` remplace `middleware.ts`.)
//
// Ce n'est qu'une première barrière : chaque page et chaque Server Action
// revérifie l'utilisateur côté serveur (lib/session.ts), comme le demande la
// doc de Next (un matcher modifié ferait sinon sauter la protection).
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { COOKIE_SECURISE, NOM_COOKIE_SESSION, configServeur } from "@/lib/supabase/env";

/** Pages ouvertes sans session. */
const PAGES_PUBLIQUES = ["/connexion", "/auth/callback"];

function estPublique(chemin: string): boolean {
  return PAGES_PUBLIQUES.some((p) => chemin === p || chemin.startsWith(`${p}/`));
}

/** Redirection sur le même hôte, en gardant les cookies de session
 * éventuellement rafraîchis. Next rend relatif l'en-tête Location quand
 * l'origine est la même (proxy n'accepte pas d'URL relative). */
function rediriger(vers: string, request: NextRequest, source: NextResponse): NextResponse {
  const cible = request.nextUrl.clone();
  cible.pathname = vers;
  cible.search = "";
  const reponse = NextResponse.redirect(cible, 307);
  for (const cookie of source.cookies.getAll()) {
    reponse.cookies.set(cookie);
  }
  const cache = source.headers.get("Cache-Control");
  if (cache) reponse.headers.set("Cache-Control", cache);
  return reponse;
}

export async function proxy(request: NextRequest) {
  let reponse = NextResponse.next({ request });
  const { url, cleAnon } = configServeur();

  const supabase = createServerClient(url, cleAnon, {
    cookieOptions: { name: NOM_COOKIE_SESSION, secure: COOKIE_SECURISE },
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (aPoser, entetes) => {
        for (const { name, value } of aPoser) request.cookies.set(name, value);
        reponse = NextResponse.next({ request });
        for (const { name, value, options } of aPoser) reponse.cookies.set(name, value, options);
        for (const [nom, valeur] of Object.entries(entetes)) reponse.headers.set(nom, valeur);
      },
    },
  });

  // getUser() interroge GoTrue : un jeton expiré ou révoqué est refusé, et la
  // session est rafraîchie (cookies réécrits par setAll ci-dessus).
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const chemin = request.nextUrl.pathname;
  if (!user && !estPublique(chemin)) {
    return rediriger("/connexion", request, reponse);
  }
  if (user && chemin === "/connexion") {
    return rediriger("/", request, reponse);
  }
  return reponse;
}

export const config = {
  matcher: [
    // Tout, sauf les fichiers de Next, les modèles d'e-mail (lus par GoTrue
    // sans session) et les fichiers statiques à extension.
    "/((?!_next/static|_next/image|modeles-email/|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|txt|html)$).*)",
  ],
};
