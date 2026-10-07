"use server";

// Création d'un groupe à partir de sa société de tête (T019, FR-004).
// L'autorisation et les données se décident ici, côté serveur : le navigateur
// n'envoie qu'un SIREN et une case de confirmation. Le nom et le statut de la
// tête sont relus dans le registre, jamais repris du formulaire.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";

import { ERREUR_INCONNUE } from "@/lib/erreurs";
import { LIBELLES_STATUT, societeParSiren } from "@/lib/recherche";
import { utilisateurCourant } from "@/lib/session";
import { creerClientAdmin } from "@/lib/supabase/admin";

import { SANS_ORGANISATION, organisationMembre } from "./organisation";

export type EtatCreation =
  | { statut: "initial" }
  | { statut: "erreur"; message: string }
  | { statut: "doublon"; message: string; groupeId: string | null };

const schema = z.object({
  siren: z.string().regex(/^[0-9]{9}$/, { error: "Le SIREN doit compter 9 chiffres." }),
  confirmation: z.boolean(),
});

export async function creerGroupe(_etat: EtatCreation, formulaire: FormData): Promise<EtatCreation> {
  const { supabase, user } = await utilisateurCourant();

  // 1. L'appelant est-il membre d'une organisation ? Lu avec SA session, sous RLS.
  const organisationId = await organisationMembre(supabase, user.id);
  if (!organisationId) {
    return { statut: "erreur", message: SANS_ORGANISATION };
  }

  const saisie = schema.safeParse({
    siren: String(formulaire.get("siren") ?? "").replace(/\s/g, ""),
    confirmation: formulaire.get("confirmation") === "oui",
  });
  if (!saisie.success) {
    return { statut: "erreur", message: saisie.error.issues[0].message };
  }
  const { siren, confirmation } = saisie.data;

  // 2. La tête existe-t-elle au registre ? Nom et statut relus à la source.
  const lu = await societeParSiren(siren);
  if (!lu.ok) {
    return { statut: "erreur", message: lu.message };
  }
  if (!lu.societe) {
    return {
      statut: "erreur",
      message: "Ce SIREN n'est pas au registre des sociétés. Vérifiez-le, ou cherchez la société par son nom.",
    };
  }
  // Une tête cessée ou radiée se choisit en connaissance de cause (cas limite de T019).
  if (lu.societe.statut !== "active" && !confirmation) {
    return {
      statut: "erreur",
      message: `Cette société est ${LIBELLES_STATUT[lu.societe.statut].toLowerCase()}. Cochez la confirmation pour en faire quand même la tête du groupe.`,
    };
  }

  // 3. Seulement ensuite, la clé service_role (aucune politique d'écriture pour
  //    authenticated sur groupes) : organisation et auteur viennent du serveur.
  const admin = creerClientAdmin();
  const { data, error } = await admin
    .from("groupes")
    .insert({
      organisation_id: organisationId,
      tete_siren: siren,
      nom: lu.societe.nom,
      cree_par: user.id,
    })
    .select("id")
    .single();

  if (error?.code === "23505") {
    // Déjà un groupe sur cette tête dans l'organisation : on mène à lui.
    const { data: existant } = await supabase
      .from("groupes")
      .select("id")
      .eq("organisation_id", organisationId)
      .eq("tete_siren", siren)
      .maybeSingle();
    return {
      statut: "doublon",
      message: "Votre organisation a déjà un groupe sur cette société de tête.",
      groupeId: (existant?.id as string | undefined) ?? null,
    };
  }
  if (error || !data) {
    console.error("création de groupe refusée", { code: error?.code });
    return { statut: "erreur", message: ERREUR_INCONNUE };
  }

  revalidatePath("/groupes");
  redirect(`/groupes/${data.id as string}`);
}
