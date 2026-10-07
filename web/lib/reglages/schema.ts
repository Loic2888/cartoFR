// Schéma des réglages d'un groupe (T020, FR-005, principe 2).
//
// Même forme que worker/cartofr/reglages.py (pydantic) : les fixtures de
// worker/tests/fixtures/reglages/ sont acceptées ou refusées pareil des deux
// côtés (C1, schema.test.ts). Sens de chaque clé :
// skills/account-mapping/references/moteur-france.md.
//
// `familles_exclues` (noms de famille en clair) est refusé : seules leurs
// empreintes HMAC entrent dans les réglages (garde-fou 6, voir empreinte.ts).
import { z } from "zod";

// Blancs reconnus des deux côtés (JavaScript et Python ne s'accordent pas sur
// `\s`) : un texte fait d'eux seuls est vide. Même motif que reglages.py.
const BLANCS = " \\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff\\u0085";
const MOTIF_TEXTE = new RegExp(`^[${BLANCS}]*[^${BLANCS}\\x00-\\x1f\\x7f][^\\x00-\\x1f\\x7f]*$`, "u");
const MOTIF_SIREN = /^[0-9]{9}$/;
const MOTIF_EMPREINTE = /^[0-9a-f]{64}$/;
export const TEXTE_MAX = 200;
export const LISTE_MAX = 1000;
export const CLE_EN_CLAIR = "familles_exclues";

/** Longueur en caractères (points de code), comme len() en Python. */
export function longueur(texte: string): number {
  return [...texte].length;
}

const texte = z
  .string({ error: (iss) => (iss.input === undefined ? "obligatoire" : "doit être un texte") })
  .regex(MOTIF_TEXTE, { error: "vide, ou contient un caractère interdit (tabulation, retour à la ligne)" })
  .refine((t) => longueur(t) <= TEXTE_MAX, { error: `${TEXTE_MAX} caractères au plus` });
const siren = z
  .string({
    error: (iss) => (iss.input === undefined ? "obligatoire" : "doit être un SIREN en texte"),
  })
  .regex(MOTIF_SIREN, { error: "un SIREN fait 9 chiffres" });
const empreinte = z
  .string({ error: "doit être une empreinte" })
  .regex(MOTIF_EMPREINTE, { error: "empreinte invalide" });

function liste<T extends z.ZodType>(element: T) {
  return z
    .array(element, { error: "doit être une liste" })
    .max(LISTE_MAX, { error: `${LISTE_MAX} éléments au plus` })
    .optional();
}

export const schemaReglages = z.strictObject(
  {
    groupe: texte,
    tete: siren,
    marques_sures: liste(texte),
    marques_ambigues: liste(texte),
    marques_sures_homonymes: liste(texte),
    marques_sigles: liste(texte),
    exclus: liste(siren),
    exclus_noms: liste(texte),
    familles_exclues_empreintes: liste(empreinte),
    priorite: liste(siren),
    organigramme: liste(texte),
  },
  { error: "clé inconnue" },
);

export type Reglages = z.infer<typeof schemaReglages>;

/** Les listes saisies dans l'écran, dans l'ordre d'affichage. Les familles
 * exclues n'y sont pas : elles ne se saisissent que par ajout (empreinte). */
export const LISTES = [
  {
    cle: "marques_sures",
    libelle: "Marques sûres",
    aide: "Propres au groupe : une société qui porte ce nom entre seule (sauf société civile).",
    siren: false,
  },
  {
    cle: "marques_ambigues",
    libelle: "Marques ambiguës",
    aide: "Prénoms, noms de famille, mots courants, lieux : une deuxième preuve est toujours exigée.",
    siren: false,
  },
  {
    cle: "marques_sures_homonymes",
    libelle: "Marques sûres homonymes",
    aide: "Marques sûres qui sont aussi un nom courant : une deuxième preuve est toujours exigée.",
    siren: false,
  },
  {
    cle: "marques_sigles",
    libelle: "Sigles",
    aide: "Deuxième preuve exigée seulement si le nom n'est guère que le sigle.",
    siren: false,
  },
  {
    cle: "organigramme",
    libelle: "Organigramme (maisons)",
    aide: "Nom légal exact de chaque maison : la plus grande société de ce nom devient tête de maison.",
    siren: false,
  },
  {
    cle: "exclus",
    libelle: "SIREN exclus",
    aide: "Sociétés à ne jamais faire entrer (actionnaire familial, groupe homonyme). 9 chiffres.",
    siren: true,
  },
  {
    cle: "exclus_noms",
    libelle: "Débuts de nom exclus",
    aide: "Toute société dont le nom commence ainsi reste hors du groupe.",
    siren: false,
  },
  {
    cle: "priorite",
    libelle: "SIREN prioritaires comme maison mère",
    aide: "À égalité de mandat, ces sociétés sont préférées comme maison mère, dans cet ordre. 9 chiffres.",
    siren: true,
  },
] as const;

export type CleListe = (typeof LISTES)[number]["cle"];

export const LIBELLES: Record<string, string> = {
  groupe: "Nom du groupe",
  tete: "Tête du groupe",
  familles_exclues_empreintes: "Familles exclues",
  ...Object.fromEntries(LISTES.map((l) => [l.cle, l.libelle])),
};

export type Verdict = { ok: true; reglages: Reglages } | { ok: false; erreurs: string[] };

/** Vérifie un contenu de réglages. Les messages, en français, nomment le
 * champ et la ligne, jamais la valeur saisie (elle peut être un nom). */
export function validerReglages(donnees: unknown): Verdict {
  if (typeof donnees !== "object" || donnees === null || Array.isArray(donnees)) {
    return { ok: false, erreurs: ["Les réglages doivent être un objet."] };
  }
  if (Object.hasOwn(donnees, CLE_EN_CLAIR)) {
    return {
      ok: false,
      erreurs: [
        "Les familles exclues ne s'enregistrent jamais en clair : seules leurs empreintes entrent dans les réglages.",
      ],
    };
  }
  const resultat = schemaReglages.safeParse(donnees);
  if (resultat.success) return { ok: true, reglages: resultat.data };
  return { ok: false, erreurs: resultat.error.issues.map(messageIssue) };
}

function messageIssue(issue: z.core.$ZodIssue): string {
  if (issue.code === "unrecognized_keys") {
    return `Clé inconnue : ${issue.keys.map((k) => k.slice(0, 40)).join(", ")}.`;
  }
  const [cle, ligne] = issue.path;
  const libelle = typeof cle === "string" ? (LIBELLES[cle] ?? cle) : "Réglages";
  const ou = typeof ligne === "number" ? `${libelle}, valeur n° ${ligne + 1}` : libelle;
  return `${ou} : ${issue.message}.`;
}
