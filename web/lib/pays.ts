// Client de la route interne `/groupe` (T050, US2) : la carto d'une société,
// déjà calculée dans la carto du pays (T048). Serveur seulement : le
// navigateur ne joint jamais le worker.
//
// - L'adresse vient de RECHERCHE_URL, fixée côté serveur : l'utilisateur ne
//   choisit que le SIREN, vérifié avant l'appel (pas de SSRF).
// - La réponse est relue par Zod, qui ne garde que les champs attendus : un
//   champ en plus (une personne, par erreur) n'arrive jamais à l'écran ni dans
//   le CSV (garde-fou 6). Une mère entrepreneur individuel n'arrive que sous
//   la forme `mere_personne_physique`, sans SIREN ni nom.
// - Aucune règle de groupe ici (principe 7) : qui descend de qui est décidé
//   par le worker.
import "server-only";

import { z } from "zod";

import type { SocieteExport } from "./cartos/csv";
import { MESSAGES_RECHERCHE } from "./recherche";

const siren = z.string().regex(/^[0-9]{9}$/);

const groupe = z.object({
  tete: siren,
  nom: z.string().nullable(),
  taille: z.number().int().nonnegative(),
});
export type GroupePays = z.infer<typeof groupe>;

const societe = z.object({
  siren,
  nom: z.string().nullable(),
  niveau: z.number().int().nonnegative(),
  maison_mere_siren: siren.nullable(),
  confiance: z.enum(["A", "B", "C"]).nullable(),
  preuve: z.string().nullable(),
  ciblable: z.boolean(),
  raison_ciblable: z.string().nullable(),
  opposition_prospection: z.boolean(),
  non_diffusible: z.boolean(),
});

const carto = z.object({
  siren,
  nom: z.string().nullable(),
  date_donnees: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .nullable(),
  groupe: groupe.nullable(),
  groupe_entier: groupe.nullable(),
  mere: z.object({ siren, nom: z.string().nullable() }).nullable(),
  mere_personne_physique: z.boolean(),
  societes: z.array(societe).min(1),
});
export type CartoPays = z.infer<typeof carto>;

export type ResultatCartoPays =
  | { ok: true; carto: CartoPays }
  | { ok: false; introuvable: boolean; status: number; message: string };

export const MESSAGES_PAYS = {
  introuvable: "Aucune société active ne porte ce SIREN dans le registre.",
  pasCalculee:
    "La carto du pays n'est pas encore calculée : elle le sera au prochain calcul de nuit. Si cela persiste, prévenez l'administrateur.",
  occupe: MESSAGES_RECHERCHE.occupe,
  absent: MESSAGES_RECHERCHE.absent,
  injoignable: MESSAGES_RECHERCHE.injoignable,
} as const;

// Mesuré le 2026-10-19 sur le vrai registre : 0,1 à 0,3 s pour VINCI (1 456 sociétés).
const DELAI_MS = 30_000;

type Options = {
  /** Remplace fetch (tests). */
  fetch?: typeof fetch;
  /** Remplace RECHERCHE_URL (tests). */
  url?: string;
  delaiMs?: number;
};

function echec(status: number, code: unknown): ResultatCartoPays {
  if (status === 404) return { ok: false, introuvable: true, status, message: MESSAGES_PAYS.introuvable };
  const message =
    status === 503 && code === "pays_absent"
      ? MESSAGES_PAYS.pasCalculee
      : status === 503 && code === "registre_absent"
        ? MESSAGES_PAYS.absent
        : status === 503
          ? MESSAGES_PAYS.occupe
          : MESSAGES_PAYS.injoignable;
  return { ok: false, introuvable: false, status: status === 503 ? 503 : 502, message };
}

/** La carto de la société `sirenDemande`, lue dans la carto du pays. */
export async function lireCartoPays(sirenDemande: string, options: Options = {}): Promise<ResultatCartoPays> {
  if (!siren.safeParse(sirenDemande).success) return echec(404, null);
  const base = options.url ?? process.env.RECHERCHE_URL;
  if (!base) {
    console.error("carto du pays : variable d'environnement manquante : RECHERCHE_URL");
    return echec(502, null);
  }
  const url = new URL("/groupe", base);
  url.searchParams.set("siren", sirenDemande);

  let r: Response;
  try {
    r = await (options.fetch ?? fetch)(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(options.delaiMs ?? DELAI_MS),
    });
  } catch (erreur) {
    console.error("carto du pays : service injoignable", { erreur: (erreur as Error)?.name });
    return echec(502, null);
  }

  let corps: unknown = null;
  try {
    corps = await r.json();
  } catch {
    corps = null;
  }
  if (!r.ok) {
    const code = (corps as { erreur?: unknown } | null)?.erreur;
    console.error("carto du pays : réponse en erreur", { statut: r.status, code });
    return echec(r.status, code);
  }
  const lu = carto.safeParse(corps);
  if (!lu.success || lu.data.siren !== sirenDemande) {
    console.error("carto du pays : réponse illisible", { statut: r.status });
    return echec(502, null);
  }
  return { ok: true, carto: lu.data };
}

/** Les lignes du CSV (mêmes colonnes que T023) : la société demandée garde le
 * SIREN de sa mère, que l'arbre affiche à part. Une mère personne physique n'a
 * pas de SIREN dans la réponse : la cellule reste vide. Sans mère, la société
 * demandée est la tête : confiance vide, écrite « Tête du groupe » comme en T023. */
export function lignesExport(c: CartoPays): SocieteExport[] {
  return c.societes.map((s) =>
    s.siren !== c.siren
      ? s
      : c.mere
        ? { ...s, maison_mere_siren: c.mere.siren }
        : { ...s, maison_mere_siren: null, confiance: null },
  );
}
