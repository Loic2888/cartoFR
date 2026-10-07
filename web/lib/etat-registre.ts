// État du registre (T014) : mise en forme de la table `etat_registre` pour
// l'écran admin. Aucune règle du moteur ici : seulement des libellés, des
// dates au format français et le calcul de fraîcheur (PRD SC-003, 7 jours).

/** Une ligne de `etat_registre`, telle que la renvoie Supabase. */
export type LigneEtatRegistre = {
  source: string;
  date_donnees: string | null;
  dernier_passage: string | null;
  statut: string | null;
  volumes: unknown;
  erreur: string | null;
};

/** Les deux sources écrites par la synchro de nuit (worker/cartofr/jobs/synchro.py). */
export const SOURCES = [
  { code: "rne", libelle: "Registre national des entreprises (INPI)" },
  { code: "sirene", libelle: "SIRENE (INSEE)" },
] as const;

/** Retard maximal des données sur le registre, en jours (PRD SC-003). */
export const FRAICHEUR_MAX_JOURS = 7;

const FUSEAU = "Europe/Paris";

export type Ton = "succes" | "en_cours" | "attention" | "echec" | "inconnu";

export type StatutLisible = { texte: string; ton: Ton };

const STATUTS: Record<string, StatutLisible> = {
  succes: { texte: "À jour", ton: "succes" },
  en_cours: { texte: "En cours", ton: "en_cours" },
  quota: { texte: "Quota INPI atteint, reprise la nuit prochaine", ton: "attention" },
  echec: { texte: "Échec", ton: "echec" },
};

/** Le statut écrit par le worker, en toutes lettres. */
export function statutLisible(statut: string | null | undefined): StatutLisible {
  if (statut == null) return { texte: "Jamais synchronisé", ton: "inconnu" };
  return STATUTS[statut] ?? { texte: "Statut inconnu", ton: "inconnu" };
}

/** `2026-10-05` → `05/10/2026`, sans passer par un fuseau (c'est une date pure). */
export function dateFr(date: string | null | undefined): string | null {
  const m = date ? /^(\d{4})-(\d{2})-(\d{2})/.exec(date) : null;
  return m ? `${m[3]}/${m[2]}/${m[1]}` : null;
}

const formatDate = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: FUSEAU,
});
const formatHeure = new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: FUSEAU,
});

/** Horodatage → `06/10/2026 à 02:00`, heure de Paris. */
export function dateHeureFr(horodatage: string | null | undefined): string | null {
  if (!horodatage) return null;
  const d = new Date(horodatage);
  if (Number.isNaN(d.getTime())) return null;
  return `${formatDate.format(d)} à ${formatHeure.format(d)}`;
}

const formatJourIso = new Intl.DateTimeFormat("en-CA", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  timeZone: FUSEAU,
});

/** Le jour calendaire à Paris, `AAAA-MM-JJ`. */
export function jourParis(maintenant: Date): string {
  return formatJourIso.format(maintenant);
}

function joursEntre(debut: string, fin: string): number {
  return Math.round((Date.parse(`${fin}T00:00:00Z`) - Date.parse(`${debut}T00:00:00Z`)) / 86_400_000);
}

export type Fraicheur =
  | { etat: "a_jour"; jours: number }
  | { etat: "perimee"; jours: number }
  | { etat: "inconnue" };

/** Âge des données : celui de la source la plus en retard, en jours à Paris.
 * Inconnue si une source n'a jamais été synchronisée. */
export function fraicheur(
  lignes: readonly Pick<LigneEtatRegistre, "source" | "date_donnees">[],
  maintenant: Date,
): Fraicheur {
  const aujourdhui = jourParis(maintenant);
  let pire = -Infinity;
  for (const { code } of SOURCES) {
    const date = lignes.find((l) => l.source === code)?.date_donnees;
    if (!date || !/^\d{4}-\d{2}-\d{2}/.test(date)) return { etat: "inconnue" };
    pire = Math.max(pire, joursEntre(date.slice(0, 10), aujourdhui));
  }
  return pire > FRAICHEUR_MAX_JOURS ? { etat: "perimee", jours: pire } : { etat: "a_jour", jours: pire };
}

/** Libellés des volumes connus, dans l'ordre d'affichage. Les clés inconnues
 * sont ignorées : le worker peut en ajouter sans casser l'écran. */
const VOLUMES: [string, string][] = [
  ["jours", "Jours appliqués"],
  ["requetes", "Requêtes envoyées"],
  ["pages", "Pages lues"],
  ["fiches", "Fiches appliquées"],
  ["ignorees", "Fiches ignorées (sans personne morale)"],
  ["invalides", "Fiches invalides"],
  ["societes_creees", "Sociétés créées"],
  ["societes_maj", "Sociétés modifiées"],
  ["societes_fermees", "Sociétés radiées"],
  ["societes_rouvertes", "Sociétés rouvertes"],
  ["liens_ouverts", "Liens ouverts"],
  ["liens_fermes", "Liens fermés"],
  ["personnes_ouvertes", "Mandats de personnes ouverts"],
  ["personnes_fermees", "Mandats de personnes fermés"],
  ["unites_lues", "Unités légales lues"],
  ["unites_legales_ajoutees", "Unités légales ajoutées"],
  ["unites_legales_modifiees", "Unités légales modifiées"],
  ["societes_ajoutees", "Sociétés ajoutées"],
  ["societes_modifiees", "Sociétés modifiées"],
  ["societes_cessees", "Sociétés cessées"],
  ["societes_reactivees", "Sociétés réactivées"],
  ["passages_non_diffusible", "Passages en non-diffusible"],
  ["sieges_lus", "Sièges lus"],
  ["sieges_ajoutes", "Sièges ajoutés"],
  ["sieges_modifies", "Sièges modifiés"],
  ["sieges_inactifs_ignores", "Sièges inactifs ignorés"],
];

const formatNombre = new Intl.NumberFormat("fr-FR");

/** Volumes d'un passage → `[libellé, nombre au format français]`. */
export function formatVolumes(volumes: unknown): { libelle: string; valeur: string }[] {
  if (volumes === null || typeof volumes !== "object" || Array.isArray(volumes)) return [];
  const v = volumes as Record<string, unknown>;
  return VOLUMES.flatMap(([cle, libelle]) => {
    const n = v[cle];
    return typeof n === "number" && Number.isFinite(n)
      ? [{ libelle, valeur: formatNombre.format(n) }]
      : [];
  });
}

/** Une carte par source, toujours les deux, dans l'ordre de SOURCES. */
export type EtatSourceAffiche = {
  code: string;
  libelle: string;
  statut: StatutLisible;
  dateDonnees: string | null;
  dernierPassage: string | null;
  volumes: { libelle: string; valeur: string }[];
  erreur: string | null;
};

export function etatsAffiches(lignes: readonly LigneEtatRegistre[]): EtatSourceAffiche[] {
  return SOURCES.map(({ code, libelle }) => {
    const l = lignes.find((x) => x.source === code);
    const statut = statutLisible(l ? l.statut : null);
    return {
      code,
      libelle,
      statut,
      dateDonnees: dateFr(l?.date_donnees),
      dernierPassage: dateHeureFr(l?.dernier_passage),
      volumes: formatVolumes(l?.volumes),
      erreur:
        statut.ton === "echec" ? (l?.erreur?.trim() || "Cause non enregistrée par la synchro.") : null,
    };
  });
}
