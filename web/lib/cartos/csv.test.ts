// Export CSV d'une carto (T023) : format Excel français, colonnes C2 et C3,
// marquages, injection de formules neutralisée, nom de fichier sûr.
// Sociétés et SIREN inventés (règle produit 6).
import { describe, expect, it } from "vitest";

import {
  BOM,
  COLONNES,
  CONFIANCE_TETE,
  type SocieteExport,
  cellule,
  construireCsv,
  contentDisposition,
  trier,
} from "./csv";

function societe(surcharges: Partial<SocieteExport> = {}): SocieteExport {
  return {
    siren: "900000002",
    nom: "ALPHAMARK SERVICES",
    niveau: 1,
    maison_mere_siren: "900000001",
    confiance: "A",
    preuve: "Mandat au registre : Président",
    ciblable: true,
    raison_ciblable: "Société opérationnelle",
    opposition_prospection: false,
    non_diffusible: false,
    ...surcharges,
  };
}

const TETE = societe({
  siren: "900000001",
  nom: "GROUPE INVENTÉ",
  niveau: 0,
  maison_mere_siren: null,
  confiance: null,
  preuve: "Tête du groupe",
  ciblable: false,
  raison_ciblable: "Holding ou société immobilière sans salarié déclaré",
});

/** Lignes sans le BOM ni la ligne vide finale. */
function lignes(csv: string): string[] {
  return csv.slice(BOM.length).split("\r\n").slice(0, -1);
}

describe("construireCsv", () => {
  const csv = construireCsv([societe(), TETE], "2026-03-04");

  it("commence par le BOM UTF-8, finit chaque ligne par CRLF, sans LF isolé", () => {
    expect(csv.startsWith("﻿")).toBe(true);
    expect(csv.endsWith("\r\n")).toBe(true);
    expect(csv.replaceAll("\r\n", "").includes("\n")).toBe(false);
    expect(new TextEncoder().encode(csv).slice(0, 3)).toEqual(new Uint8Array([0xef, 0xbb, 0xbf]));
  });

  it("écrit l'en-tête français, séparé par des points-virgules", () => {
    expect(lignes(csv)[0]).toBe(
      "SIREN;Nom;Niveau;Maison mère (SIREN);Preuve;Confiance;Ciblable;Raison (ciblable);" +
        "opposition_prospection;non_diffusible;Date des données",
    );
  });

  it("porte la date des données (C2) et les colonnes opposition_prospection et non_diffusible (C3)", () => {
    expect(COLONNES).toContain("Date des données");
    expect(COLONNES).toContain("opposition_prospection");
    expect(COLONNES).toContain("non_diffusible");
    for (const ligne of lignes(csv).slice(1)) {
      expect(ligne.endsWith(";04/03/2026")).toBe(true);
    }
  });

  it("une ligne par société, la tête d'abord, chaque ligne avec toutes les colonnes", () => {
    const corps = lignes(csv).slice(1);
    expect(corps).toHaveLength(2);
    expect(corps[0]).toBe(
      `900000001;GROUPE INVENTÉ;0;;Tête du groupe;${CONFIANCE_TETE};Non;` +
        "Holding ou société immobilière sans salarié déclaré;Non;Non;04/03/2026",
    );
    expect(corps[1]).toBe(
      "900000002;ALPHAMARK SERVICES;1;900000001;Mandat au registre : Président;A;Oui;" +
        "Société opérationnelle;Non;Non;04/03/2026",
    );
    for (const ligne of corps) expect(ligne.split(";")).toHaveLength(COLONNES.length);
  });

  it("garde une société opposée ou non diffusible, marquée Oui, jamais cachée", () => {
    const sortie = lignes(
      construireCsv(
        [
          societe({ siren: "900000003", nom: "OPPOSÉE", opposition_prospection: true }),
          societe({ siren: "900000004", nom: "NON DIFFUSIBLE", non_diffusible: true }),
        ],
        "2026-03-04",
      ),
    ).slice(1);
    expect(sortie).toHaveLength(2);
    expect(sortie.find((l) => l.startsWith("900000003"))?.split(";").slice(8, 10)).toEqual(["Oui", "Non"]);
    expect(sortie.find((l) => l.startsWith("900000004"))?.split(";").slice(8, 10)).toEqual(["Non", "Oui"]);
  });

  it("garde les accents tels quels", () => {
    expect(csv).toContain("GROUPE INVENTÉ");
    expect(csv).toContain("Maison mère (SIREN)");
  });

  it("date des données inconnue : un tiret, pas une date inventée", () => {
    expect(lignes(construireCsv([TETE], null))[1].endsWith(";—")).toBe(true);
  });

  it("carto vide : l'en-tête seul", () => {
    expect(lignes(construireCsv([], "2026-03-04"))).toHaveLength(1);
  });

  it("ne modifie pas le tableau reçu", () => {
    const entree = [societe(), TETE];
    construireCsv(entree, "2026-03-04");
    expect(entree[0].siren).toBe("900000002");
  });
});

describe("cellule : guillemets RFC 4180", () => {
  it("laisse un texte simple tel quel", () => {
    expect(cellule("ALPHAMARK")).toBe("ALPHAMARK");
    expect(cellule(3)).toBe("3");
    expect(cellule(null)).toBe("");
  });

  it("met entre guillemets un texte avec séparateur, guillemet ou saut de ligne, et double les guillemets", () => {
    expect(cellule("A;B")).toBe('"A;B"');
    expect(cellule('LA "MAISON"')).toBe('"LA ""MAISON"""');
    expect(cellule("ligne 1\nligne 2")).toBe('"ligne 1\nligne 2"');
    expect(cellule("ligne 1\r\nligne 2")).toBe('"ligne 1\r\nligne 2"');
  });

  it("une preuve avec point-virgule reste une seule colonne", () => {
    const ligne = lignes(construireCsv([societe({ preuve: "Marque ; adresse" })], "2026-03-04"))[1];
    expect(ligne).toContain(';"Marque ; adresse";');
  });
});

describe("cellule : injection de formules neutralisée", () => {
  it.each([
    ['=HYPERLINK("http://exemple.invalid","clic")', `"'=HYPERLINK(""http://exemple.invalid"",""clic"")"`],
    ["+1", "'+1"],
    ["-2", "'-2"],
    ["@SUM(A1:A2)", "'@SUM(A1:A2)"],
    ["\tTAB", "'\tTAB"],
    ["\r=1", `"'\r=1"`],
  ])("%j est préfixé d'une apostrophe", (entree, attendu) => {
    expect(cellule(entree)).toBe(attendu);
  });

  it("un nom de société piégé ne devient pas une formule dans le fichier", () => {
    const ligne = lignes(construireCsv([societe({ nom: "=1+1" })], "2026-03-04"))[1];
    expect(ligne.split(";")[1]).toBe("'=1+1");
  });

  it("aucune cellule du fichier ne commence par un caractère de formule", () => {
    const piege = societe({ nom: "@x", preuve: "+y", raison_ciblable: "-z" });
    for (const ligne of lignes(construireCsv([piege], "2026-03-04"))) {
      for (const c of ligne.split(";")) expect(c).not.toMatch(/^[=+\-@\t\r]/);
    }
  });
});

describe("trier", () => {
  it("par niveau, puis nom en ordre français, puis SIREN", () => {
    const tri = trier([
      societe({ siren: "900000005", niveau: 2, nom: "B" }),
      societe({ siren: "900000004", niveau: 1, nom: "Émeraude" }),
      societe({ siren: "900000003", niveau: 1, nom: "zeta" }),
      societe({ siren: "900000002", niveau: 1, nom: "Ab" }),
      societe({ siren: "900000001", niveau: 1, nom: "Ab" }),
      TETE,
    ]);
    expect(tri.map((s) => s.siren)).toEqual([
      "900000001",
      "900000001",
      "900000002",
      "900000004",
      "900000003",
      "900000005",
    ]);
  });
});

describe("contentDisposition", () => {
  it("nomme le fichier d'après le groupe et la date des données", () => {
    expect(contentDisposition("Groupe Inventé", "2026-03-04")).toBe(
      `attachment; filename="cartofr-groupe-invente-2026-03-04.csv"; ` +
        `filename*=UTF-8''cartofr-groupe-invent%C3%A9-2026-03-04.csv`,
    );
  });

  it("un nom de groupe piégé ne sort ni guillemet, ni point-virgule, ni saut de ligne", () => {
    const entete = contentDisposition('Evil"; filename="x.exe\r\nSet-Cookie: a=b', "2026-03-04");
    expect(entete).not.toMatch(/[\r\n]/);
    expect(entete.match(/"/g)).toHaveLength(2);
    expect(entete).toContain('filename="cartofr-evil-filename-x-exe-set-cookie-a-b-2026-03-04.csv"');
  });

  it("nom sans lettre ni chiffre, ou date invalide : valeurs de repli", () => {
    expect(contentDisposition('"";\n', "pas une date")).toContain('filename="cartofr-groupe-sans-date.csv"');
  });

  it("nom très long : coupé à 60 caractères", () => {
    const nom = /filename="cartofr-(.*)-2026-03-04\.csv"/.exec(contentDisposition("a".repeat(200), "2026-03-04"));
    expect(nom?.[1]).toHaveLength(60);
  });
});
