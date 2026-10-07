"use server";

// Envoi du lien magique (T009). Seul l'e-mail est demandé (RGPD, minimisation).
import { z } from "zod";

import { messageErreurAuth } from "@/lib/erreurs";
import { creerClientServeur } from "@/lib/supabase/server";

export type EtatEnvoi =
  | { statut: "initial" }
  | { statut: "envoye" }
  | { statut: "erreur"; message: string };

const schema = z.object({
  email: z.email({ error: "Saisissez une adresse e-mail valide, par exemple nom@entreprise.fr." }),
});

/** Codes qui veulent dire « pas de compte pour cette adresse ». On répond
 * comme pour un envoi réussi : la page ne dit pas qui a un compte. */
const SANS_COMPTE = new Set(["otp_disabled", "signup_disabled", "user_not_found"]);

export async function envoyerLien(_etat: EtatEnvoi, formulaire: FormData): Promise<EtatEnvoi> {
  const saisie = schema.safeParse({ email: String(formulaire.get("email") ?? "").trim() });
  if (!saisie.success) {
    return { statut: "erreur", message: saisie.error.issues[0].message };
  }

  const supabase = await creerClientServeur();
  // Inscription fermée : shouldCreateUser à false, un compte n'existe que sur
  // invitation. GoTrue refuse aussi (GOTRUE_DISABLE_SIGNUP, infra/).
  const { error } = await supabase.auth.signInWithOtp({
    email: saisie.data.email,
    options: { shouldCreateUser: false },
  });

  if (error && !(error.code && SANS_COMPTE.has(error.code))) {
    // Jamais l'adresse dans le journal (RGPD) : le code et le statut suffisent.
    console.error("connexion : envoi du lien refusé", { code: error.code, statut: error.status });
    return { statut: "erreur", message: messageErreurAuth(error) };
  }
  return { statut: "envoye" };
}
