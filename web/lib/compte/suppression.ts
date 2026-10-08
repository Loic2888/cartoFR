// Suppression de son propre compte (T031, règle produit 4) : la décision,
// séparée de Supabase pour être testée sans session (suppression.test.ts).
// compte/actions.ts branche un Depot sur GoTrue.
//
// Règles :
// - on ne supprime que le compte de la session en cours, jamais un identifiant
//   envoyé par le navigateur ;
// - confirmation explicite : l'utilisateur tape le mot SUPPRIMER ;
// - session expirée : rien n'est supprimé, on demande de se reconnecter ;
// - double clic : le bouton est désactivé pendant l'envoi ; si une seconde
//   demande arrive quand même et que GoTrue ne trouve plus le compte, c'est
//   un succès (il est déjà supprimé), pas une erreur ;
// - la session est fermée après la suppression, jamais avant : un échec de
//   la suppression laisse l'utilisateur connecté, avec un message.
//
// Ce que devient l'organisation est décidé en base (migration 0005) : groupes,
// réglages et cartos restent, sans référence au compte ; s'il était le seul
// administrateur, le membre le plus ancien est promu. `consequences` ne fait
// que l'annoncer avant la confirmation.

export const MOT_DE_CONFIRMATION = "SUPPRIMER";

export const MESSAGES = {
  confirmation: `Pour confirmer, tapez ${MOT_DE_CONFIRMATION} dans le champ, en lettres capitales.`,
  sessionExpiree:
    "Votre session a expiré : votre compte n'a pas été supprimé. Reconnectez-vous, puis recommencez.",
  echec:
    "La suppression n'a pas abouti : votre compte est intact. Réessayez dans quelques minutes, et si l'erreur persiste, prévenez l'administrateur.",
} as const;

export type EtatSuppression = { statut: "initial" } | { statut: "erreur"; message: string; session?: boolean };

export interface Depot {
  /** Identifiant du compte de la session en cours ; null si la session a expiré. */
  utilisateurCourant(): Promise<string | null>;
  /** Supprime le compte dans GoTrue (auth.users). */
  supprimerUtilisateur(userId: string): Promise<"ok" | "introuvable" | "erreur">;
  /** Ferme la session de ce navigateur (cookies effacés). Ne lève jamais. */
  fermerSession(): Promise<void>;
}

/** Le mot tapé confirme-t-il la suppression ? Espaces aux bords ignorés, casse exacte. */
export function confirmationValide(saisie: unknown): boolean {
  return typeof saisie === "string" && saisie.trim() === MOT_DE_CONFIRMATION;
}

/** Rend `null` quand le compte est supprimé (l'appelant redirige), sinon l'état d'erreur. */
export async function supprimerCompteAvec(
  depot: Depot,
  saisie: unknown,
): Promise<EtatSuppression | null> {
  const userId = await depot.utilisateurCourant();
  if (!userId) return { statut: "erreur", message: MESSAGES.sessionExpiree, session: true };
  if (!confirmationValide(saisie)) return { statut: "erreur", message: MESSAGES.confirmation };

  const issue = await depot.supprimerUtilisateur(userId);
  if (issue === "erreur") return { statut: "erreur", message: MESSAGES.echec };
  await depot.fermerSession();
  return null;
}

export type Appartenance = {
  organisationId: string;
  userId: string;
  role: string;
  creeLe: string;
};

export type Consequence = {
  organisationId: string;
  /** Ce qui arrive à l'organisation quand ce compte disparaît. */
  cas: "rien" | "promotion" | "sans_membre";
};

/** Pour chaque organisation du compte, ce que la base fera à sa suppression
 * (même règle que public.membres_garder_un_admin, migration 0005). `membres` :
 * toutes les appartenances lisibles par l'utilisateur (RLS : ses organisations). */
export function consequences(membres: Appartenance[], userId: string): Consequence[] {
  const miennes = membres.filter((m) => m.userId === userId);
  return miennes.map(({ organisationId, role }) => {
    const autres = membres.filter((m) => m.organisationId === organisationId && m.userId !== userId);
    if (autres.length === 0) return { organisationId, cas: "sans_membre" };
    if (role === "admin" && !autres.some((m) => m.role === "admin")) {
      return { organisationId, cas: "promotion" };
    }
    return { organisationId, cas: "rien" };
  });
}
