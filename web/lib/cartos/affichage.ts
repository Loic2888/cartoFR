// Affichage des cartos d'un groupe (T021) : libellés français des statuts,
// durée, et ce qui permet de lancer une carto. Aucune règle du moteur ici
// (principe 7) : seulement de quoi afficher ce que le worker a écrit.
//
// Sans dépendance serveur : importé par la page et par le composant client.

export const STATUTS = ["en_attente", "en_cours", "terminee", "echec"] as const;
export type StatutCarto = (typeof STATUTS)[number];

/** Le statut en texte (le sens ne passe jamais par la seule couleur ou l'icône). */
export const LIBELLE_STATUT: Record<StatutCarto, string> = {
  en_attente: "En attente",
  en_cours: "En cours",
  terminee: "Terminée",
  echec: "Échec",
};

/** Une carto qui n'est pas finie : la page se rafraîchit tant qu'il y en a une. */
export function estActive(statut: string): boolean {
  return statut === "en_attente" || statut === "en_cours";
}

/** Une carto en attente sans travail depuis plus longtemps que ça est orpheline
 * (lancement interrompu entre l'insertion de la carto et celle du travail) :
 * elle ne bloque plus un nouveau lancement et ne fait plus rafraîchir la page. */
export const ORPHELINE_APRES_MS = 10 * 60 * 1000;

/** Une carto qui bloque un nouveau lancement du même groupe : active, et pas orpheline. */
export function bloquante(
  carto: { statut: string; travail_id: number | string | null; cree_le: string },
  maintenant: number,
): boolean {
  if (!estActive(carto.statut)) return false;
  const orpheline =
    carto.statut === "en_attente" &&
    carto.travail_id === null &&
    maintenant - new Date(carto.cree_le).getTime() > ORPHELINE_APRES_MS;
  return !orpheline;
}

/** Une au moins des cartos d'un groupe bloque un nouveau lancement. */
export function uneBloquante(
  cartos: { statut: string; travail_id: number | string | null; cree_le: string }[],
  maintenant: number = Date.now(),
): boolean {
  return cartos.some((c) => bloquante(c, maintenant));
}

export function libelleStatut(statut: string): string {
  return (LIBELLE_STATUT as Record<string, string>)[statut] ?? "Statut inconnu";
}

/** Durée d'un calcul, en français : « 850 ms », « 12 s », « 1 min 04 s ». Tiret si inconnue. */
export function dureeFr(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const secondes = Math.round(ms / 1000);
  if (secondes < 60) return `${secondes} s`;
  const minutes = Math.floor(secondes / 60);
  const reste = String(secondes % 60).padStart(2, "0");
  return `${minutes} min ${reste} s`;
}

/** Date « AAAA-MM-JJ » (colonne date de Postgres) en « JJ/MM/AAAA », sans fuseau. Tiret si vide. */
export function dateDonneesFr(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "—";
}

export const MESSAGES = {
  groupeIntrouvable: "Ce groupe n'existe pas, ou vous n'y avez pas accès.",
  aucuneVersionValidee:
    "Aucune version des réglages n'est validée : le moteur ne tourne que sur des réglages validés. Validez une version dans les réglages, puis lancez la carto.",
  dejaEnCours:
    "Une carto de ce groupe est déjà en attente ou en cours. Attendez qu'elle se termine avant d'en lancer une autre.",
  lancee: "Carto lancée. Elle apparaît ci-dessous, et la page se met à jour toute seule.",
  base: "Le lancement a échoué. Réessayez dans un instant, et si cela persiste, prévenez l'administrateur.",
} as const;

/** Peut-on lancer une carto ? Il faut une version validée, et aucune carto déjà active. */
export function peutLancer(etat: {
  versionValidee: boolean;
  cartoActive: boolean;
}): { ok: true } | { ok: false; message: string } {
  if (!etat.versionValidee) return { ok: false, message: MESSAGES.aucuneVersionValidee };
  if (etat.cartoActive) return { ok: false, message: MESSAGES.dejaEnCours };
  return { ok: true };
}
