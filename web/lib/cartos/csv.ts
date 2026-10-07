// Export CSV d'une carto (T023, FR-007, SC-005) : le livrable au client.
//
// Fonctions pures, sans dépendance serveur : la route d'export
// (groupes/[id]/cartos/[cartoId]/export/route.ts) lit les lignes avec la
// session de l'utilisateur et les passe ici. Aucune règle du moteur
// (principe 7) : on met en forme ce que le worker a écrit dans carto_societes.
//
// Aucun nom de personne (garde-fou 6) : les colonnes sont celles de
// carto_societes, qui n'a aucune colonne de personne physique (principe 6) ;
// `nom` est la dénomination de la société, et `preuve` un texte du moteur que
// worker/tests/test_aucune_personne.py confronte aux dirigeants du registre.
//
// Format pour Excel en français : UTF-8 avec BOM (sinon Excel lit du
// Windows-1252 et casse les accents), séparateur `;`, fin de ligne CRLF,
// guillemets selon la RFC 4180. Une cellule qui commence par = + - @,
// tabulation ou retour chariot est préfixée d'une apostrophe : sans quoi Excel
// l'exécuterait comme une formule (injection CSV, recommandation OWASP).

import { dateDonneesFr } from "./affichage";

/** Une ligne de carto_societes, telle que lue en base. */
export type SocieteExport = {
  siren: string;
  nom: string | null;
  niveau: number;
  maison_mere_siren: string | null;
  confiance: string | null;
  preuve: string | null;
  ciblable: boolean;
  raison_ciblable: string | null;
  opposition_prospection: boolean;
  non_diffusible: boolean;
};

/** Les colonnes, dans l'ordre. `opposition_prospection` et `non_diffusible`
 * gardent leur nom technique (critère C3 de T023) : c'est sous ce nom que le
 * marquage est connu du client et de la licence INPI. */
export const COLONNES = [
  "SIREN",
  "Nom",
  "Niveau",
  "Maison mère (SIREN)",
  "Preuve",
  "Confiance",
  "Ciblable",
  "Raison (ciblable)",
  "opposition_prospection",
  "non_diffusible",
  "Date des données",
] as const;

export const SEPARATEUR = ";";
export const FIN_DE_LIGNE = "\r\n";
export const BOM = "﻿";

/** La tête n'entre pas par un lien : elle n'a pas de confiance. */
export const CONFIANCE_TETE = "Tête du groupe";

const DEBUT_DE_FORMULE = /^[=+\-@\t\r]/;
const A_GUILLEMETER = /[;"\r\n]/;

/** Une cellule prête à écrire : neutralisée contre les formules, puis entre
 * guillemets si elle contient le séparateur, un guillemet ou un saut de ligne. */
export function cellule(valeur: string | number | null | undefined): string {
  let texte = valeur === null || valeur === undefined ? "" : String(valeur);
  if (DEBUT_DE_FORMULE.test(texte)) texte = `'${texte}`;
  if (A_GUILLEMETER.test(texte)) texte = `"${texte.replaceAll('"', '""')}"`;
  return texte;
}

function ouiNon(valeur: boolean): string {
  return valeur ? "Oui" : "Non";
}

/** Ordre de l'arbre : niveau, puis nom (ordre français), puis SIREN. */
export function trier(societes: readonly SocieteExport[]): SocieteExport[] {
  const comparateur = new Intl.Collator("fr", { sensitivity: "base", numeric: true });
  return [...societes].sort(
    (a, b) =>
      a.niveau - b.niveau ||
      comparateur.compare(a.nom ?? "", b.nom ?? "") ||
      (a.siren < b.siren ? -1 : a.siren > b.siren ? 1 : 0),
  );
}

/** Le CSV complet, BOM compris. `dateDonnees` : colonne date de `cartos`
 * (AAAA-MM-JJ), écrite JJ/MM/AAAA sur chaque ligne. */
export function construireCsv(societes: readonly SocieteExport[], dateDonnees: string | null): string {
  const date = dateDonneesFr(dateDonnees);
  const lignes = [COLONNES.map(cellule).join(SEPARATEUR)];
  for (const s of trier(societes)) {
    lignes.push(
      [
        s.siren,
        s.nom,
        s.niveau,
        s.maison_mere_siren,
        s.preuve,
        s.confiance ?? CONFIANCE_TETE,
        ouiNon(s.ciblable),
        s.raison_ciblable,
        ouiNon(s.opposition_prospection),
        ouiNon(s.non_diffusible),
        date,
      ]
        .map(cellule)
        .join(SEPARATEUR),
    );
  }
  return BOM + lignes.join(FIN_DE_LIGNE) + FIN_DE_LIGNE;
}

/** Slug d'un nom de groupe : lettres et chiffres, le reste devient un tiret.
 * `ascii` retire aussi les accents. Jamais vide, jamais plus de 60 caractères. */
function slug(nom: string, ascii: boolean): string {
  let texte = nom.normalize(ascii ? "NFKD" : "NFC").toLowerCase();
  if (ascii) texte = texte.replace(/\p{M}/gu, "");
  const autorise = ascii ? /[^a-z0-9]+/g : /[^\p{L}\p{N}]+/gu;
  const sortie = texte.replace(autorise, "-").replace(/^-+|-+$/g, "").slice(0, 60).replace(/-+$/, "");
  return sortie || "groupe";
}

/** En-tête Content-Disposition : `cartofr-<groupe>-<aaaa-mm-jj>.csv`, en ASCII
 * pour `filename` et en UTF-8 (RFC 5987) pour `filename*`. Le nom du groupe
 * est saisi par un utilisateur : seuls lettres, chiffres et tirets en sortent,
 * jamais un guillemet, un point-virgule ou un saut de ligne. */
export function contentDisposition(nomGroupe: string, date: string | null): string {
  const jour = /^\d{4}-\d{2}-\d{2}$/.test(date ?? "") ? (date as string) : "sans-date";
  const ascii = `cartofr-${slug(nomGroupe, true)}-${jour}.csv`;
  const utf8 = `cartofr-${slug(nomGroupe, false)}-${jour}.csv`;
  return `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(utf8)}`;
}
