// Erreurs de Supabase Auth traduites en français (T009, règle produit 1).
// Chaque message dit ce qui s'est passé et quoi faire. Aucun texte anglais de
// GoTrue n'arrive jusqu'à l'écran.

/** Ce qu'on lit d'une erreur : AuthError de supabase-js, ou un simple code
 * (paramètre `erreur` de l'URL, renvoyé par /auth/callback). */
type ErreurAuth = {
  code?: string;
  name?: string;
  status?: number;
  message?: string;
};

const LIEN_EXPIRE =
  "Ce lien de connexion a expiré ou a déjà servi. Demandez-en un nouveau ci-dessous.";
const LIEN_INVALIDE =
  "Ce lien de connexion n'est pas valide. Demandez-en un nouveau ci-dessous.";
const TROP_DE_DEMANDES =
  "Trop de demandes en peu de temps. Attendez une minute avant de redemander un lien.";
const SANS_COMPTE =
  "Aucun compte n'existe pour cette adresse. Demandez une invitation à l'administrateur de votre organisation.";
const SESSION_EXPIREE = "Votre session a expiré. Reconnectez-vous pour continuer.";
const INJOIGNABLE =
  "Le service de connexion ne répond pas. Vérifiez votre connexion, puis réessayez dans quelques minutes.";
export const ERREUR_INCONNUE =
  "Une erreur inattendue s'est produite. Réessayez, et si elle persiste, prévenez l'administrateur.";

/** Codes d'erreur de GoTrue (et quelques codes à nous), vers leur message. */
const MESSAGES: Record<string, string> = {
  // Lien magique ou d'invitation
  otp_expired: LIEN_EXPIRE,
  flow_state_expired: LIEN_EXPIRE,
  flow_state_not_found: LIEN_EXPIRE,
  bad_code_verifier: LIEN_INVALIDE,
  bad_jwt: LIEN_INVALIDE,
  lien_invalide: LIEN_INVALIDE,
  // Envois trop rapprochés
  over_email_send_rate_limit: TROP_DE_DEMANDES,
  over_request_rate_limit: TROP_DE_DEMANDES,
  // Inscription fermée : on n'entre que sur invitation
  signup_disabled: SANS_COMPTE,
  otp_disabled: SANS_COMPTE,
  user_not_found: SANS_COMPTE,
  email_not_confirmed:
    "Votre invitation n'a pas encore été acceptée. Ouvrez le lien de l'e-mail d'invitation, ou demandez-en un nouveau.",
  invalid_credentials: "Identifiants invalides. Demandez un nouveau lien de connexion.",
  // Saisie
  email_address_invalid: "Cette adresse e-mail n'est pas valide. Vérifiez-la et réessayez.",
  validation_failed: "Cette adresse e-mail n'est pas valide. Vérifiez-la et réessayez.",
  // Invitation d'un membre
  email_exists: "Cette adresse a déjà un compte cartoFR. Elle ne peut pas être invitée une seconde fois.",
  user_already_exists:
    "Cette adresse a déjà un compte cartoFR. Elle ne peut pas être invitée une seconde fois.",
  not_admin: "Seul un administrateur de l'organisation peut faire cela.",
  // Session
  session_expired: SESSION_EXPIREE,
  session_not_found: SESSION_EXPIREE,
  refresh_token_not_found: SESSION_EXPIREE,
  refresh_token_already_used: SESSION_EXPIREE,
  // Réseau
  reseau: INJOIGNABLE,
};

function estErreurReseau(erreur: ErreurAuth): boolean {
  if (erreur.name === "AuthRetryableFetchError") return true;
  if (erreur.status === 0) return true;
  const message = erreur.message?.toLowerCase() ?? "";
  return message.includes("fetch failed") || message.includes("failed to fetch");
}

/** Message français pour une erreur d'auth. Toujours une phrase utilisable,
 * jamais le texte brut de GoTrue. */
export function messageErreurAuth(erreur: unknown): string {
  if (erreur === null || erreur === undefined) return ERREUR_INCONNUE;
  const e: ErreurAuth =
    typeof erreur === "string" ? { code: erreur } : typeof erreur === "object" ? erreur : {};
  if (e.code && Object.hasOwn(MESSAGES, e.code)) return MESSAGES[e.code];
  if (estErreurReseau(e)) return INJOIGNABLE;
  if (e.status === 429) return TROP_DE_DEMANDES;
  return ERREUR_INCONNUE;
}

/** Code court, sûr à placer dans une URL (`/connexion?erreur=…`) : seulement
 * des lettres minuscules et des soulignés, sinon `lien_invalide`. */
export function codeErreurPourUrl(code: string | null | undefined): string {
  return code && /^[a-z_]{1,40}$/.test(code) ? code : "lien_invalide";
}
