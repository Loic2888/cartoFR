// T051, C5 : l'écran des corrections ne parle plus de validation. Plus aucune
// étape « valider » : une version enregistrée s'applique (principe 2 amendé).
//
// Deux sources de texte visible : le source des trois fichiers de l'écran
// (commentaires retirés), et les messages que la logique renvoie à l'écran
// après un enregistrement. On cherche les formes françaises du verbe et du nom
// (valider, validez, validé·e·s, validation) et « brouillon ». Les identifiants
// internes (`validerReglages`, l'origine « validee » écrite par le worker,
// `aria-invalid`) ne sont pas des formes françaises : ils ne déclenchent rien.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { MESSAGES as MESSAGES_CARTOS } from "@/lib/cartos/affichage";
import { MESSAGES } from "@/lib/reglages/operations";
import { MESSAGES_PROPOSITION } from "@/lib/reglages/proposition";
import { MESSAGES_RECALCUL } from "@/lib/reglages/recalcul";

const DOSSIER = path.dirname(fileURLToPath(import.meta.url));
const FICHIERS = ["page.tsx", "editeur-reglages.tsx", "proposition.tsx"];
const INTERDIT = /\bvalid(?:er|ez|ons|é|ée|és|ées|ation)(?![a-zà-ÿ])|brouillon/i;

/** Le source sans ses commentaires : blocs JSX, blocs, et `//` jusqu'en fin de ligne (sauf
 * dans une URL, « https:// »). */
function sansCommentaires(source: string): string {
  return source
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

function lire(fichier: string): string {
  return sansCommentaires(readFileSync(path.join(DOSSIER, fichier), "utf8"));
}

describe("écran des corrections (C5)", () => {
  it.each(FICHIERS)("%s : aucun libellé « valider », aucun brouillon", (fichier) => {
    expect(lire(fichier)).not.toMatch(INTERDIT);
  });

  it("les messages affichés après un enregistrement n'en parlent pas non plus", () => {
    const messages = [MESSAGES, MESSAGES_PROPOSITION, MESSAGES_RECALCUL, MESSAGES_CARTOS].flatMap((m) =>
      Object.values(m),
    );
    for (const message of messages) expect(message).not.toMatch(INTERDIT);
  });

  it("le bouton dit ce qu'il fait : enregistrer et recalculer", () => {
    expect(lire("editeur-reglages.tsx")).toContain("Enregistrer et recalculer");
    expect(lire("proposition.tsx")).toContain("Enregistrer et recalculer");
  });

  it("le motif attrape bien les formes visibles", () => {
    for (const texte of ["Valider", "validez-la", "Version validée", "déjà validé.", "la validation", "brouillon"]) {
      expect(texte).toMatch(INTERDIT);
    }
    for (const texte of ["validerReglages", '"validee"', "aria-invalid", "deja_valide_en"]) {
      expect(texte).not.toMatch(INTERDIT);
    }
  });
});
