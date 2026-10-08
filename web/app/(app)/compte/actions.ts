"use server";

// Suppression de son propre compte (T031, règle produit 4). La décision est
// dans lib/compte/suppression.ts (testée) ; ici, on branche GoTrue.
//
// Le compte supprimé est TOUJOURS celui de la session, lu côté serveur : le
// formulaire n'envoie que le mot de confirmation. La clé service_role ne sert
// qu'après cette lecture, pour appeler l'API d'administration de GoTrue, qui
// efface la ligne auth.users ; la base fait le reste (migrations 0001, 0002,
// 0005) : appartenances supprimées, cree_par et valide_par à nul, cartos
// gardées par l'organisation, un administrateur gardé.
import { redirect } from "next/navigation";

import { type Depot, type EtatSuppression, MESSAGES, supprimerCompteAvec } from "@/lib/compte/suppression";
import { creerClientAdmin } from "@/lib/supabase/admin";
import { creerClientServeur } from "@/lib/supabase/server";

export async function supprimerMonCompte(
  _etat: EtatSuppression,
  formulaire: FormData,
): Promise<EtatSuppression> {
  const supabase = await creerClientServeur();

  const depot: Depot = {
    async utilisateurCourant() {
      // getUser interroge GoTrue : une session expirée ou un compte déjà
      // supprimé rendent null, jamais un identifiant périmé.
      const {
        data: { user },
      } = await supabase.auth.getUser();
      return user?.id ?? null;
    },
    async supprimerUtilisateur(userId) {
      const { error } = await creerClientAdmin().auth.admin.deleteUser(userId);
      if (!error) return "ok";
      if (error.status === 404 || error.code === "user_not_found") return "introuvable";
      // Code et statut seulement : ni identifiant, ni adresse dans le journal (RGPD).
      console.error("suppression de compte refusée par GoTrue", { code: error.code, statut: error.status });
      return "erreur";
    },
    async fermerSession() {
      try {
        // Le compte n'existe plus : GoTrue peut refuser la révocation, les
        // cookies de ce navigateur sont effacés quand même.
        await supabase.auth.signOut({ scope: "local" });
      } catch {
        console.error("suppression de compte : session locale non fermée");
      }
    },
  };

  let etat: EtatSuppression | null;
  try {
    etat = await supprimerCompteAvec(depot, formulaire.get("confirmation"));
  } catch {
    console.error("suppression de compte : erreur inattendue");
    etat = { statut: "erreur", message: MESSAGES.echec };
  }
  if (etat) return etat;
  redirect("/connexion?compte=supprime");
}
