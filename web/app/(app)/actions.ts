"use server";

import { redirect } from "next/navigation";

import { creerClientServeur } from "@/lib/supabase/server";

/** Déconnexion : ferme la session (cookies effacés), retour à /connexion. */
export async function deconnecter() {
  const supabase = await creerClientServeur();
  await supabase.auth.signOut();
  redirect("/connexion");
}
