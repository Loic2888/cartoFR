"use server";

// Invitation d'un membre (T009). L'autorisation se décide ici, côté serveur,
// avec la session de l'appelant : jamais d'après ce que le navigateur envoie.
import { revalidatePath } from "next/cache";
import { z } from "zod";

import { messageErreurAuth } from "@/lib/erreurs";
import { organisationAdministree, utilisateurCourant } from "@/lib/session";
import { creerClientAdmin } from "@/lib/supabase/admin";

export type EtatInvitation =
  | { statut: "initial" }
  | { statut: "envoye"; email: string }
  | { statut: "erreur"; message: string };

// Seul l'e-mail est collecté (RGPD, minimisation) : ni nom, ni fonction.
const schema = z.object({
  email: z.email({ error: "Saisissez une adresse e-mail valide, par exemple nom@entreprise.fr." }),
});

export async function inviterMembre(
  _etat: EtatInvitation,
  formulaire: FormData,
): Promise<EtatInvitation> {
  const { supabase, user } = await utilisateurCourant();

  // 1. L'appelant est-il admin ? Lu avec SA session, sous RLS.
  const organisationId = await organisationAdministree(supabase, user.id);
  if (!organisationId) {
    return { statut: "erreur", message: messageErreurAuth("not_admin") };
  }

  const saisie = schema.safeParse({
    email: String(formulaire.get("email") ?? "").trim().toLowerCase(),
  });
  if (!saisie.success) {
    return { statut: "erreur", message: saisie.error.issues[0].message };
  }

  // 2. Seulement ensuite, la clé service_role : création du compte et e-mail
  //    d'invitation (modèle français, infra/), puis l'appartenance.
  const admin = creerClientAdmin();
  const { data, error } = await admin.auth.admin.inviteUserByEmail(saisie.data.email);
  if (error || !data.user) {
    // Code et statut seulement : jamais l'adresse dans le journal (RGPD).
    console.error("invitation refusée par GoTrue", { code: error?.code, statut: error?.status });
    return { statut: "erreur", message: messageErreurAuth(error) };
  }

  // Réinviter une adresse dont l'invitation attend encore : GoTrue renvoie
  // l'e-mail et rend le même compte. L'appartenance existe déjà, on la garde
  // telle quelle (ni doublon, ni changement de rôle). On n'efface jamais le
  // compte en cas d'échec : il peut appartenir à une autre organisation.
  const { error: erreurMembre } = await admin
    .from("membres")
    .upsert(
      { organisation_id: organisationId, user_id: data.user.id, role: "membre" },
      { onConflict: "organisation_id,user_id", ignoreDuplicates: true },
    );
  if (erreurMembre) {
    console.error("invitation : ajout du membre impossible", { code: erreurMembre.code });
    return {
      statut: "erreur",
      message:
        "L'invitation est partie, mais le membre n'a pas pu être ajouté à l'organisation. Renvoyez l'invitation.",
    };
  }

  revalidatePath("/admin/membres");
  return { statut: "envoye", email: saisie.data.email };
}
