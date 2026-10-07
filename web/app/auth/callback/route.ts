// Retour du lien magique ou d'invitation (T009) : ouvre la session, puis
// renvoie à l'accueil. En cas d'échec, retour à /connexion avec un code
// d'erreur, que la page traduit et sous lequel elle propose un nouveau lien.
//
// Deux formes de lien :
// - `token_hash` + `type` : celle de nos modèles d'e-mail (public/modeles-email),
//   qui marche même si le lien est ouvert sur un autre appareil ;
// - `code` : flux PKCE de supabase-js, au cas où un lien GoTrue par défaut
//   serait envoyé (modèles indisponibles).
// La destination est toujours `/` : aucun paramètre ne choisit où l'on va
// (pas de redirection ouverte).
import type { EmailOtpType } from "@supabase/supabase-js";
import type { NextRequest } from "next/server";

import { codeErreurPourUrl } from "@/lib/erreurs";
import { creerClientServeur } from "@/lib/supabase/server";

const TYPES_ACCEPTES: readonly EmailOtpType[] = ["email", "magiclink", "invite"];

function estTypeAccepte(type: string | null): type is EmailOtpType {
  return TYPES_ACCEPTES.includes(type as EmailOtpType);
}

/** Redirection relative (derrière Caddy, l'URL vue par Next est interne). */
function rediriger(vers: string): Response {
  return new Response(null, { status: 303, headers: { Location: vers } });
}

function echec(code: string | null | undefined): Response {
  return rediriger(`/connexion?erreur=${codeErreurPourUrl(code)}`);
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;

  // GoTrue renvoie ici ses propres erreurs (lien expiré…) en paramètres.
  if (params.has("error_code") || params.has("error")) {
    return echec(params.get("error_code"));
  }

  const supabase = await creerClientServeur();
  const tokenHash = params.get("token_hash");
  const type = params.get("type");
  const code = params.get("code");

  let erreur: { code?: string } | null = null;
  if (tokenHash && estTypeAccepte(type)) {
    ({ error: erreur } = await supabase.auth.verifyOtp({ token_hash: tokenHash, type }));
  } else if (code) {
    ({ error: erreur } = await supabase.auth.exchangeCodeForSession(code));
  } else {
    return echec("lien_invalide");
  }

  if (erreur) {
    return echec(erreur.code);
  }
  return rediriger("/");
}
