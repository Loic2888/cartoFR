// Client de la route interne de recherche du registre (T019, ARCHI « Recherche
// de la tête »). Serveur seulement : le navigateur ne joint jamais le worker.
//
// - L'adresse vient de RECHERCHE_URL (http://recherche:8080 dans Docker), fixée
//   côté serveur : l'utilisateur ne choisit que le texte cherché, jamais l'hôte
//   ni le chemin (pas de SSRF).
// - La réponse est relue par Zod, qui ne garde que les champs de société
//   attendus : un champ en plus (une personne, par erreur) n'arrive jamais à
//   l'écran (garde-fou 6).
// - Chaque échec devient une phrase en français (règle produit 1). Le texte
//   cherché n'est jamais journalisé : ce peut être un nom de personne (RGPD).
import "server-only";

import { z } from "zod";

export const STATUTS = ["active", "cessee", "radiee"] as const;
export type Statut = (typeof STATUTS)[number];

export const LIBELLES_STATUT: Record<Statut, string> = {
  active: "Active",
  cessee: "Cessée",
  radiee: "Radiée",
};

const societe = z.object({
  siren: z.string().regex(/^[0-9]{9}$/),
  nom: z.string().min(1),
  sigle: z.string().nullable(),
  ville: z.string().nullable(),
  statut: z.enum(STATUTS),
});
export type Societe = z.infer<typeof societe>;

const reponse = z.object({ resultats: z.array(societe).max(20) });

export type ResultatRecherche =
  | { ok: true; societes: Societe[] }
  | { ok: false; message: string };

export const MESSAGES_RECHERCHE = {
  occupe:
    "La recherche est momentanément indisponible (mise à jour du registre). Réessayez dans quelques minutes.",
  absent:
    "La recherche n'est pas disponible : le registre des sociétés n'est pas encore chargé. Prévenez l'administrateur.",
  tropCourte: "Saisissez au moins 2 caractères, ou un SIREN à 9 chiffres.",
  tropLongue: "Votre recherche est trop longue : 100 caractères au plus.",
  injoignable:
    "Le service de recherche ne répond pas. Réessayez dans quelques minutes ; si cela persiste, prévenez l'administrateur.",
} as const;

// Mesuré le 2026-10-07 sur le vrai registre : 1,5 à 3,5 s à chaud, 16 s pour
// la première recherche après le démarrage (registre pas encore en cache).
const DELAI_MS = 30_000;

type Options = {
  /** Remplace fetch (tests). */
  fetch?: typeof fetch;
  /** Remplace RECHERCHE_URL (tests). */
  url?: string;
  delaiMs?: number;
};

/** Message français pour une réponse en erreur du service. */
export function messagePourStatut(statut: number, code: unknown): string {
  if (statut === 503 && code === "registre_absent") return MESSAGES_RECHERCHE.absent;
  if (statut === 503) return MESSAGES_RECHERCHE.occupe;
  if (statut === 400 && code === "requete_trop_longue") return MESSAGES_RECHERCHE.tropLongue;
  if (statut === 400) return MESSAGES_RECHERCHE.tropCourte;
  return MESSAGES_RECHERCHE.injoignable;
}

/** Cherche des sociétés par nom, sigle ou SIREN : 20 au plus. */
export async function chercherSocietes(q: string, options: Options = {}): Promise<ResultatRecherche> {
  const base = options.url ?? process.env.RECHERCHE_URL;
  if (!base) {
    console.error("recherche : variable d'environnement manquante : RECHERCHE_URL");
    return { ok: false, message: MESSAGES_RECHERCHE.injoignable };
  }
  // Seul le paramètre q vient de l'utilisateur, encodé ; l'hôte et le chemin sont fixes.
  const url = new URL("/recherche", base);
  url.searchParams.set("q", q);

  let r: Response;
  try {
    r = await (options.fetch ?? fetch)(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(options.delaiMs ?? DELAI_MS),
    });
  } catch (erreur) {
    // Nom de l'erreur seulement : l'URL contient le texte cherché.
    console.error("recherche : service injoignable", { erreur: (erreur as Error)?.name });
    return { ok: false, message: MESSAGES_RECHERCHE.injoignable };
  }

  let corps: unknown = null;
  try {
    corps = await r.json();
  } catch {
    corps = null;
  }
  if (!r.ok) {
    const code = (corps as { erreur?: unknown } | null)?.erreur;
    console.error("recherche : réponse en erreur", { statut: r.status, code });
    return { ok: false, message: messagePourStatut(r.status, code) };
  }
  const lu = reponse.safeParse(corps);
  if (!lu.success) {
    console.error("recherche : réponse illisible", { statut: r.status });
    return { ok: false, message: MESSAGES_RECHERCHE.injoignable };
  }
  return { ok: true, societes: lu.data.resultats };
}

/** La société de ce SIREN au registre, ou null si le registre ne la connaît pas. */
export async function societeParSiren(
  siren: string,
  options: Options = {},
): Promise<{ ok: true; societe: Societe | null } | { ok: false; message: string }> {
  const resultat = await chercherSocietes(siren, options);
  if (!resultat.ok) return resultat;
  return { ok: true, societe: resultat.societes.find((s) => s.siren === siren) ?? null };
}
