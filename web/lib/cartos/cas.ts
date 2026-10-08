// Cas douteux d'une carto et décision du consultant (T028, FR-009).
//
// Le moteur range les cas et les écrit dans `carto_cas` (T027) ; ici, on les
// affiche et on enregistre la décision. Aucune règle du moteur (principe 7) :
// la décision est reprise par le worker à la carto suivante
// (cartofr.moteur.decisions_en_vigueur), pas appliquée par l'interface.
//
// Règles d'écriture :
// - le cas est lu avec la session de l'utilisateur (RLS) : un cas d'une autre
//   organisation, ou d'une carto d'un autre groupe que celui de l'adresse, est
//   introuvable, rien n'est écrit ;
// - l'organisation et le groupe de la décision sont ceux du cas ainsi lu,
//   jamais une valeur envoyée par le navigateur ;
// - l'auteur est l'utilisateur connecté (identifiant auth.users), la date est
//   posée par la base (`decide_le`). Une décision n'est jamais modifiée : une
//   nouvelle décision la remplace.
//
// Sans dépendance serveur : importé par la page, l'action et le composant client.

export const TYPES_CAS = ["confiance_c", "co_entreprise", "participation", "etrangere", "decision"] as const;
export type TypeCas = (typeof TYPES_CAS)[number];

export const DECISIONS = ["retenir", "ecarter"] as const;
export type Decision = (typeof DECISIONS)[number];

/** Pourquoi le cas est douteux, en toutes lettres. */
export const LIBELLE_TYPE: Record<TypeCas, string> = {
  confiance_c: "Confiance C",
  co_entreprise: "Co-entreprise",
  participation: "Participation sans contrôle",
  etrangere: "Société étrangère",
  decision: "Déjà tranché",
};

export function libelleType(type: string): string {
  return (LIBELLE_TYPE as Record<string, string>)[type] ?? "Autre cas";
}

/** L'état d'une décision, en phrase : « Retenue », « Écartée ». */
export const LIBELLE_DECISION: Record<Decision, string> = {
  retenir: "Retenue",
  ecarter: "Écartée",
};

export function estDecision(valeur: unknown): valeur is Decision {
  return typeof valeur === "string" && (DECISIONS as readonly string[]).includes(valeur);
}

/** Une ligne de `carto_cas`, telle que la page la lit. */
export type CasCarto = {
  siren: string;
  nom: string | null;
  types: string[];
  regle: string;
  retenue: boolean;
  indices_pour: string[];
  indices_contre: string[];
  decision: string | null;
};

/** Une ligne de `decisions`, telle que la page la lit. */
export type DecisionLue = {
  id: number;
  siren: string;
  decision: string;
  decide_le: string;
  decide_par: string | null;
};

/** Pour l'affichage, la dernière décision enregistrée par SIREN : la plus récente, et à date
 * égale la dernière enregistrée. C'est l'ordre que le worker applique ; le worker reste seul à
 * en tirer la carto suivante. */
export function dernieresDecisions(decisions: DecisionLue[]): Map<string, DecisionLue> {
  const dernieres = new Map<string, DecisionLue>();
  for (const d of decisions) {
    if (!estDecision(d.decision)) continue;
    const actuelle = dernieres.get(d.siren);
    const le = Date.parse(d.decide_le);
    const avant = actuelle ? Date.parse(actuelle.decide_le) : Number.NEGATIVE_INFINITY;
    const plusRecente = !actuelle || le > avant || (le === avant && d.id > actuelle.id);
    if (plusRecente) dernieres.set(d.siren, d);
  }
  return dernieres;
}

/** Qui a décidé : l'utilisateur lui-même, l'e-mail d'un membre de l'organisation (lu côté
 * serveur, lib/cartos/auteurs.ts), un ancien membre, ou un compte effacé (decide_par à nul). */
export function auteurFr(decidePar: string | null, moi: string, emails: ReadonlyMap<string, string>): string {
  if (decidePar === null) return "par un compte supprimé";
  if (decidePar === moi) return "par vous";
  const email = emails.get(decidePar);
  return email ? `par ${email}` : "par un ancien membre";
}

const dateFr = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "Europe/Paris",
});
const heureFr = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" });

/** « Écartée le 08/10/2026 à 10:12, par vous ». */
export function decisionFr(
  d: Pick<DecisionLue, "decision" | "decide_le" | "decide_par">,
  moi: string,
  emails: ReadonlyMap<string, string>,
): string {
  const etat = estDecision(d.decision) ? LIBELLE_DECISION[d.decision] : "Décision inconnue";
  const le = new Date(d.decide_le);
  return `${etat} le ${dateFr.format(le)} à ${heureFr.format(le)}, ${auteurFr(d.decide_par, moi, emails)}`;
}

export const MESSAGES = {
  introuvable: "Ce cas n'existe pas, ou vous n'y avez pas accès.",
  base: "La décision n'a pas pu être enregistrée. Réessayez dans un instant, et si cela persiste, prévenez l'administrateur.",
  retenir: "Décision enregistrée : la société sera retenue à la prochaine carto du groupe.",
  ecarter: "Décision enregistrée : la société sera écartée à la prochaine carto du groupe.",
} as const;

export interface DepotCas {
  /** Le cas, lu sous RLS avec sa carto ; null s'il n'existe pas, appartient à une autre
   * organisation, ou si la carto n'est pas du groupe donné. */
  lireCas(
    groupeId: string,
    cartoId: string,
    siren: string,
  ): Promise<{ organisationId: string; groupeId: string } | null>;
  /** Insère la décision ; rend sa date (posée par la base), ou "erreur". */
  insererDecision(ligne: {
    organisationId: string;
    groupeId: string;
    cartoId: string;
    siren: string;
    decision: Decision;
    auteur: string;
  }): Promise<{ decideLe: string } | "erreur">;
}

export type Resultat =
  | { statut: "ok"; message: string; decision: Decision; decideLe: string }
  | { statut: "erreur"; message: string };

export async function deciderAvec(
  depot: DepotCas,
  auteur: string,
  demande: { groupeId: string; cartoId: string; siren: string; decision: Decision },
): Promise<Resultat> {
  const cas = await depot.lireCas(demande.groupeId, demande.cartoId, demande.siren);
  if (!cas) return { statut: "erreur", message: MESSAGES.introuvable };
  const inseree = await depot.insererDecision({
    organisationId: cas.organisationId,
    groupeId: cas.groupeId,
    cartoId: demande.cartoId,
    siren: demande.siren,
    decision: demande.decision,
    auteur,
  });
  if (inseree === "erreur") return { statut: "erreur", message: MESSAGES.base };
  return {
    statut: "ok",
    message: MESSAGES[demande.decision],
    decision: demande.decision,
    decideLe: inseree.decideLe,
  };
}
