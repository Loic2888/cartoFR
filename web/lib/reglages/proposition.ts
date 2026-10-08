// Proposition des réglages par l'IA : la demander, la revoir, valider ce qui
// en sort (T026, FR-008, SC-007).
//
// L'IA propose dans le worker (travail `proposition`, T025) ; ici on ne
// décide rien sur le groupe (principe 7). On met un travail en file, puis on
// applique ce que le consultant a choisi pour chaque élément : accepter,
// corriger ou rejeter, plus ses ajouts. La version qui en sort est validée
// d'un coup, avec son nombre de corrections (SC-007) ; la proposition, elle,
// n'est jamais validée telle quelle (migration 0004, principe 1).
//
// Une correction, c'est : un élément rejeté, un élément corrigé dont la
// valeur ou la liste change, ou un élément ajouté. Accepter, ou « corriger »
// sans rien changer, n'en est pas une.
//
// Logique testée sans base ni session (proposition.test.ts) ; le dépôt
// Supabase est dans depot-proposition.ts.
import { z } from "zod";

import { MESSAGES, type Groupe, type Resultat, lignes } from "./operations";
import { LISTES, type Reglages, validerReglages } from "./schema";

/** Les listes que l'IA remplit, dans l'ordre d'affichage. */
export const LISTES_PROPOSEES = [
  "marques_sures",
  "marques_ambigues",
  "marques_sigles",
  "organigramme",
  "exclus_noms",
] as const;
export type ListeProposee = (typeof LISTES_PROPOSEES)[number];

export const LIBELLES_LISTES: Record<ListeProposee, string> = Object.fromEntries(
  LISTES.filter((l) => (LISTES_PROPOSEES as readonly string[]).includes(l.cle)).map((l) => [
    l.cle,
    l.libelle,
  ]),
) as Record<ListeProposee, string>;

const schemaElement = z.object({
  liste: z.enum(LISTES_PROPOSEES),
  valeur: z.string(),
  source: z.string(),
  homonymes: z.number().int().min(0).nullable().optional(),
});
export type Element = z.infer<typeof schemaElement>;

const schemaProposition = z.object({ modele: z.string(), elements: z.array(schemaElement) });

/** Les éléments d'une proposition lue en base, ou null si elle est illisible. */
export function lireElements(proposition: unknown): Element[] | null {
  const lu = schemaProposition.safeParse(proposition);
  return lu.success ? lu.data.elements : null;
}

/** Une source s'affiche comme lien seulement en http(s). */
export function sourceSure(source: string): string | null {
  try {
    const url = new URL(source);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

export type Decision =
  | { choix: "accepter" }
  | { choix: "rejeter" }
  | { choix: "corriger"; valeur: string; liste: ListeProposee };

export type Ajout = { liste: ListeProposee; valeur: string };

export type Revue =
  | { ok: true; contenu: Record<string, unknown>; corrections: number }
  | { ok: false; message: string };

/** Applique la revue du consultant au contenu proposé : les listes proposées
 * sont reconstruites à partir des décisions et des ajouts ; les autres clés
 * (groupe, tête, exclusions par SIREN, empreintes…) restent celles de la
 * proposition. Rend aussi le nombre de corrections. */
export function appliquerRevue(
  contenuPropose: Record<string, unknown>,
  elements: Element[],
  decisions: Decision[],
  ajouts: Ajout[],
): Revue {
  if (decisions.length !== elements.length) {
    return { ok: false, message: "La revue ne correspond plus à la proposition : rechargez la page." };
  }
  const contenu: Record<string, unknown> = { ...contenuPropose };
  const listes = Object.fromEntries(LISTES_PROPOSEES.map((l) => [l, [] as string[]])) as Record<
    ListeProposee,
    string[]
  >;
  const ajouter = (liste: ListeProposee, valeur: string) => {
    if (!listes[liste].includes(valeur)) listes[liste].push(valeur);
  };

  let corrections = 0;
  for (const [i, e] of elements.entries()) {
    const d = decisions[i];
    if (d.choix === "accepter") {
      ajouter(e.liste, e.valeur);
    } else if (d.choix === "rejeter") {
      corrections += 1;
    } else {
      const valeur = d.valeur.trim();
      if (!valeur) {
        return { ok: false, message: `Élément n° ${i + 1} : la valeur corrigée est vide.` };
      }
      if (valeur !== e.valeur || d.liste !== e.liste) corrections += 1;
      ajouter(d.liste, valeur);
    }
  }
  const vus = new Set<string>();
  for (const a of ajouts) {
    for (const valeur of lignes(a.valeur)) {
      const cle = `${a.liste}\u0000${valeur}`;
      if (vus.has(cle)) continue;
      vus.add(cle);
      corrections += 1;
      ajouter(a.liste, valeur);
    }
  }
  for (const l of LISTES_PROPOSEES) contenu[l] = listes[l];
  return { ok: true, contenu, corrections };
}

export type VersionProposee = {
  id: string;
  version: number;
  origine: string;
  contenu: Reglages;
  proposition: unknown;
  valideLe: string | null;
};

export type TravailProposition = {
  statut: "en_attente" | "en_cours" | "termine" | "echec";
  erreur: string | null;
  creeLe: string;
};

export interface DepotProposition {
  /** Le groupe, lu sous RLS ; null s'il n'existe pas ou appartient à une autre organisation. */
  lireGroupe(groupeId: string): Promise<Groupe | null>;
  /** La version de numéro le plus haut du groupe, ou null. */
  derniereVersion(groupeId: string): Promise<VersionProposee | null>;
  /** Le dernier travail `proposition` du groupe, ou null. */
  dernierTravail(groupeId: string): Promise<TravailProposition | null>;
  /** Met un travail `proposition` en file. */
  insererTravail(ligne: {
    organisationId: string;
    groupeId: string;
    demandePar: string;
  }): Promise<"ok" | "erreur">;
  /** Insère une version déjà validée, tirée d'une proposition ; "conflit" si
   * ce numéro existe déjà. */
  insererVersionValidee(ligne: {
    groupeId: string;
    organisationId: string;
    version: number;
    contenu: Reglages;
    propositionId: string;
    corrections: number;
    par: string;
    le: string;
  }): Promise<"ok" | "conflit" | "erreur">;
}

export const MESSAGES_PROPOSITION = {
  dejaEnCours: "Une proposition est déjà en cours pour ce groupe : patientez, puis rechargez la page.",
  enFile:
    "Proposition demandée. L'IA lit le site et le rapport annuel du groupe : comptez quelques minutes, puis rechargez la page.",
  pasDeProposition: "La dernière version de ce groupe n'est pas une proposition à revoir : rechargez la page.",
  illisible: "Cette proposition est illisible. Demandez-en une nouvelle.",
} as const;

/** Un travail en attente ou en cours empêche d'en demander un autre. */
export function propositionEnCours(travail: TravailProposition | null): boolean {
  return travail !== null && (travail.statut === "en_attente" || travail.statut === "en_cours");
}

/** Ce qu'on dit du dernier travail, s'il y a quelque chose à dire. Un échec
 * plus ancien que la dernière version est de l'histoire ancienne. Le texte
 * d'erreur ne porte qu'un nom de classe (T008) : on le traduit. */
export function etatTravail(travail: TravailProposition | null, derniereVersionLe: string | null): string | null {
  if (!travail) return null;
  if (travail.statut === "en_attente") return "Proposition demandée : elle attend son tour dans la file.";
  if (travail.statut === "en_cours") {
    return "L'IA prépare la proposition. Comptez quelques minutes, puis rechargez la page.";
  }
  if (travail.statut === "echec") {
    if (derniereVersionLe && derniereVersionLe > travail.creeLe) return null;
    if (travail.erreur?.includes("CleIaManquante")) {
      return "La proposition a échoué : le serveur n'a pas de clé pour l'IA. Prévenez l'administrateur.";
    }
    if (travail.erreur?.includes("RegistreIndisponible")) {
      return "La proposition a échoué : le registre est indisponible pour le moment. Réessayez plus tard.";
    }
    return "La proposition a échoué. Réessayez ; si l'échec se répète, prévenez l'administrateur.";
  }
  return null;
}

export async function demanderPropositionAvec(
  depot: DepotProposition,
  userId: string,
  groupeId: string,
): Promise<Resultat> {
  const groupe = await depot.lireGroupe(groupeId);
  if (!groupe) return { statut: "erreur", message: MESSAGES.groupeIntrouvable };
  if (propositionEnCours(await depot.dernierTravail(groupe.id))) {
    return { statut: "erreur", message: MESSAGES_PROPOSITION.dejaEnCours };
  }
  const insertion = await depot.insererTravail({
    organisationId: groupe.organisationId,
    groupeId: groupe.id,
    demandePar: userId,
  });
  if (insertion === "erreur") return { statut: "erreur", message: MESSAGES.base };
  const derniere = await depot.derniereVersion(groupe.id);
  return { statut: "ok", version: derniere?.version ?? 0, message: MESSAGES_PROPOSITION.enFile };
}

export type EntreeRevue = {
  groupeId: string;
  version: number;
  decisions: Decision[];
  ajouts: Ajout[];
};

export async function validerPropositionAvec(
  depot: DepotProposition,
  userId: string,
  entree: EntreeRevue,
  maintenant: () => Date = () => new Date(),
): Promise<Resultat & { corrections?: number }> {
  const groupe = await depot.lireGroupe(entree.groupeId);
  if (!groupe) return { statut: "erreur", message: MESSAGES.groupeIntrouvable };

  const derniere = await depot.derniereVersion(groupe.id);
  if (!derniere || derniere.origine !== "proposition" || derniere.valideLe) {
    return { statut: "erreur", message: MESSAGES_PROPOSITION.pasDeProposition };
  }
  if (derniere.version !== entree.version) return { statut: "erreur", message: MESSAGES.versionChangee };

  const elements = lireElements(derniere.proposition);
  if (!elements) return { statut: "erreur", message: MESSAGES_PROPOSITION.illisible };

  const revue = appliquerRevue(derniere.contenu, elements, entree.decisions, entree.ajouts);
  if (!revue.ok) return { statut: "erreur", message: revue.message };
  const verdict = validerReglages(revue.contenu);
  if (!verdict.ok) return { statut: "erreur", message: verdict.erreurs.join(" ") };

  const numero = derniere.version + 1;
  const insertion = await depot.insererVersionValidee({
    groupeId: groupe.id,
    organisationId: groupe.organisationId,
    version: numero,
    contenu: verdict.reglages,
    propositionId: derniere.id,
    corrections: revue.corrections,
    par: userId,
    le: maintenant().toISOString(),
  });
  if (insertion === "conflit") return { statut: "erreur", message: MESSAGES.versionChangee };
  if (insertion === "erreur") return { statut: "erreur", message: MESSAGES.base };
  const n = revue.corrections;
  return {
    statut: "ok",
    version: numero,
    corrections: n,
    message: `Version ${numero} validée, ${n === 0 ? "sans correction" : n === 1 ? "avec 1 correction" : `avec ${n} corrections`} de la proposition. Elle servira aux prochaines cartos.`,
  };
}
