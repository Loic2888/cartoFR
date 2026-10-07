// Enregistrer un brouillon de réglages, valider une version (T020, FR-005).
//
// La logique de décision vit ici, séparée de actions.ts, pour être testée
// sans base ni session (operations.test.ts, C2) : actions.ts ne fait que
// brancher un Depot sur Supabase.
//
// Règles :
// - on lit le groupe avec la session de l'utilisateur (RLS) : un groupe d'une
//   autre organisation est introuvable, donc ni brouillon ni validation ;
// - un brouillon ne s'enregistre que sur la dernière version ouverte, et une
//   validation ne porte que sur la dernière version, encore en brouillon (C2) ;
// - chaque version porte son auteur ; la validation, son validateur et sa
//   date (C4) ;
// - les familles exclues : le nom saisi devient une empreinte, ici, et n'est
//   ni stocké, ni journalisé, ni renvoyé (garde-fou 6). Les empreintes déjà
//   enregistrées viennent de la base, jamais du navigateur.
import { empreinte } from "./empreinte";
import { LISTES, type CleListe, type Reglages, validerReglages } from "./schema";

export type Groupe = { id: string; organisationId: string; teteSiren: string; nom: string };

export type Version = {
  id: string;
  version: number;
  contenu: Reglages;
  valideLe: string | null;
};

export interface Depot {
  /** Le groupe, lu sous RLS avec la session de l'utilisateur ; null s'il
   * n'existe pas ou appartient à une autre organisation. */
  lireGroupe(groupeId: string): Promise<Groupe | null>;
  /** La version de numéro le plus haut du groupe, ou null. */
  derniereVersion(groupeId: string): Promise<Version | null>;
  /** Insère une version ; "conflit" si ce numéro existe déjà (course). */
  insererVersion(ligne: {
    groupeId: string;
    organisationId: string;
    version: number;
    contenu: Reglages;
    creePar: string;
  }): Promise<"ok" | "conflit" | "erreur">;
  /** Pose valide_le et valide_par, seulement si la version n'est pas encore
   * validée. Rend false si aucune ligne n'a changé. */
  marquerValidee(versionId: string, validePar: string, valideLe: string): Promise<boolean | "erreur">;
}

export type Resultat = { statut: "ok"; version: number; message: string } | { statut: "erreur"; message: string };

export const MESSAGES = {
  groupeIntrouvable: "Ce groupe n'existe pas, ou vous n'y avez pas accès.",
  versionChangee: "Les réglages ont changé depuis votre ouverture : rechargez la page.",
  dejaValidee: "Cette version est déjà validée.",
  rienAValider: "Ce groupe n'a encore aucune version de réglages à valider.",
  rienNaChange: "Rien n'a changé : aucune nouvelle version n'a été créée.",
  cleManquante:
    "Le serveur n'a pas de clé d'empreinte : impossible d'ajouter une famille exclue. Prévenez l'administrateur.",
  base: "L'enregistrement a échoué. Réessayez dans un instant, et si cela persiste, prévenez l'administrateur.",
} as const;

/** Un brouillon part de la version que l'utilisateur a ouverte : elle doit
 * être encore la dernière (0 quand le groupe n'a aucune version). */
export function peutEnregistrer(derniere: number | null, base: number): boolean {
  return (derniere ?? 0) === base;
}

/** Une validation porte sur la dernière version, si elle est en brouillon. */
export function peutValider(
  derniere: { version: number; valideLe: string | null } | null,
  demandee: number,
): "ok" | "pas_la_derniere" | "deja_validee" | "aucune" {
  if (!derniere) return "aucune";
  if (derniere.version !== demandee) return "pas_la_derniere";
  if (derniere.valideLe) return "deja_validee";
  return "ok";
}

/** Une liste saisie dans un champ texte, une valeur par ligne : blancs des
 * bords retirés, lignes vides et doublons ôtés, ordre gardé. */
export function lignes(texte: string): string[] {
  const vues = new Set<string>();
  const sortie: string[] = [];
  for (const brute of texte.split(/\r\n|\r|\n/)) {
    const valeur = brute.trim();
    if (valeur && !vues.has(valeur)) {
      vues.add(valeur);
      sortie.push(valeur);
    }
  }
  return sortie;
}

export type Saisie = {
  groupeId: string;
  baseVersion: number;
  listes: Record<CleListe, string>;
  /** Noms de famille à exclure, un par ligne. Jamais stockés en clair. */
  famillesAjoutees: string;
  retirerFamilles: boolean;
};

/** Le contenu d'une nouvelle version : groupe et tête viennent du groupe, les
 * listes de la saisie, les empreintes de la base (plus les nouvelles). */
export function construireContenu(
  groupe: Groupe,
  saisie: Saisie,
  empreintesActuelles: string[],
  cle: string | null,
): { ok: true; contenu: unknown } | { ok: false; message: string } {
  const noms = lignes(saisie.famillesAjoutees);
  if (noms.length > 0 && !cle) return { ok: false, message: MESSAGES.cleManquante };
  const base = saisie.retirerFamilles ? [] : empreintesActuelles;
  const nouvelles = noms.map((n) => empreinte(n, cle as string));
  const empreintes = [...new Set([...base, ...nouvelles])];

  const contenu: Record<string, unknown> = { groupe: groupe.nom, tete: groupe.teteSiren };
  for (const { cle: c, siren } of LISTES) {
    const valeurs = lignes(saisie.listes[c] ?? "");
    // Un SIREN s'écrit souvent avec des espaces : « 775 670 417 ».
    contenu[c] = siren ? valeurs.map((v) => v.replace(/[\s  ]/g, "")) : valeurs;
  }
  contenu.familles_exclues_empreintes = empreintes;
  return { ok: true, contenu };
}

function memeContenu(a: unknown, b: unknown): boolean {
  return JSON.stringify(normaliserPourComparer(a)) === JSON.stringify(normaliserPourComparer(b));
}

function normaliserPourComparer(contenu: unknown): Record<string, unknown> {
  const c = (contenu ?? {}) as Record<string, unknown>;
  const sortie: Record<string, unknown> = { groupe: c.groupe, tete: c.tete };
  for (const { cle } of LISTES) sortie[cle] = c[cle] ?? [];
  sortie.familles_exclues_empreintes = c.familles_exclues_empreintes ?? [];
  return sortie;
}

export async function enregistrerBrouillonAvec(
  depot: Depot,
  userId: string,
  saisie: Saisie,
  cle: string | null,
): Promise<Resultat> {
  const groupe = await depot.lireGroupe(saisie.groupeId);
  if (!groupe) return { statut: "erreur", message: MESSAGES.groupeIntrouvable };

  const derniere = await depot.derniereVersion(groupe.id);
  if (!peutEnregistrer(derniere?.version ?? null, saisie.baseVersion)) {
    return { statut: "erreur", message: MESSAGES.versionChangee };
  }

  const construit = construireContenu(
    groupe,
    saisie,
    derniere?.contenu.familles_exclues_empreintes ?? [],
    cle,
  );
  if (!construit.ok) return { statut: "erreur", message: construit.message };

  const verdict = validerReglages(construit.contenu);
  if (!verdict.ok) return { statut: "erreur", message: verdict.erreurs.join(" ") };

  if (derniere && memeContenu(derniere.contenu, verdict.reglages)) {
    return { statut: "erreur", message: MESSAGES.rienNaChange };
  }

  const numero = (derniere?.version ?? 0) + 1;
  const insertion = await depot.insererVersion({
    groupeId: groupe.id,
    organisationId: groupe.organisationId,
    version: numero,
    contenu: verdict.reglages,
    creePar: userId,
  });
  // Conflit : quelqu'un a enregistré ce numéro entre notre lecture et notre
  // écriture. Ses changements priment : on ne réessaie pas par-dessus.
  if (insertion === "conflit") return { statut: "erreur", message: MESSAGES.versionChangee };
  if (insertion === "erreur") return { statut: "erreur", message: MESSAGES.base };
  return {
    statut: "ok",
    version: numero,
    message: `Version ${numero} enregistrée en brouillon. Validez-la pour qu'elle serve aux cartos.`,
  };
}

export async function validerAvec(
  depot: Depot,
  userId: string,
  entree: { groupeId: string; version: number },
  maintenant: () => Date = () => new Date(),
): Promise<Resultat> {
  const groupe = await depot.lireGroupe(entree.groupeId);
  if (!groupe) return { statut: "erreur", message: MESSAGES.groupeIntrouvable };

  const derniere = await depot.derniereVersion(groupe.id);
  const decision = peutValider(derniere, entree.version);
  if (decision === "aucune") return { statut: "erreur", message: MESSAGES.rienAValider };
  if (decision === "pas_la_derniere") return { statut: "erreur", message: MESSAGES.versionChangee };
  if (decision === "deja_validee") return { statut: "erreur", message: MESSAGES.dejaValidee };

  // Le contenu est revérifié avant validation : une version mal formée ne
  // doit jamais servir au moteur.
  const verdict = validerReglages(derniere!.contenu);
  if (!verdict.ok) return { statut: "erreur", message: verdict.erreurs.join(" ") };

  const marque = await depot.marquerValidee(derniere!.id, userId, maintenant().toISOString());
  if (marque === "erreur") return { statut: "erreur", message: MESSAGES.base };
  // Aucune ligne changée : validée entre-temps par quelqu'un d'autre.
  if (!marque) return { statut: "erreur", message: MESSAGES.dejaValidee };
  return {
    statut: "ok",
    version: entree.version,
    message: `Version ${entree.version} validée : elle servira aux prochaines cartos.`,
  };
}
