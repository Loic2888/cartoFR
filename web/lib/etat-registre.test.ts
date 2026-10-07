import { describe, expect, it } from "vitest";

import {
  dateFr,
  dateHeureFr,
  etatsAffiches,
  formatVolumes,
  fraicheur,
  jourParis,
  statutLisible,
  type LigneEtatRegistre,
} from "./etat-registre";

const ligne = (source: string, champs: Partial<LigneEtatRegistre> = {}): LigneEtatRegistre => ({
  source,
  date_donnees: "2026-10-05",
  dernier_passage: "2026-10-06T00:00:00Z",
  statut: "succes",
  volumes: {},
  erreur: null,
  ...champs,
});

describe("statutLisible", () => {
  it("écrit chaque statut du worker en toutes lettres", () => {
    expect(statutLisible("succes").texte).toBe("À jour");
    expect(statutLisible("en_cours").texte).toBe("En cours");
    expect(statutLisible("quota").texte).toBe("Quota INPI atteint, reprise la nuit prochaine");
    expect(statutLisible("echec")).toEqual({ texte: "Échec", ton: "echec" });
  });

  it("ne laisse jamais un statut sans texte", () => {
    expect(statutLisible(null)).toEqual({ texte: "Jamais synchronisé", ton: "inconnu" });
    expect(statutLisible("bizarre")).toEqual({ texte: "Statut inconnu", ton: "inconnu" });
  });
});

describe("dates", () => {
  it("formate une date pure en jj/mm/aaaa sans décalage de fuseau", () => {
    expect(dateFr("2026-01-01")).toBe("01/01/2026");
    expect(dateFr(null)).toBeNull();
    expect(dateFr("pas une date")).toBeNull();
  });

  it("formate un horodatage à l'heure de Paris", () => {
    // 23:30 UTC le 31/12 = 00:30 le 01/01 à Paris (hiver, UTC+1).
    expect(dateHeureFr("2026-12-31T23:30:00Z")).toBe("01/01/2027 à 00:30");
    // Été, UTC+2.
    expect(dateHeureFr("2026-10-06T00:05:00Z")).toBe("06/10/2026 à 02:05");
    expect(dateHeureFr(null)).toBeNull();
    expect(dateHeureFr("n'importe quoi")).toBeNull();
  });

  it("prend le jour calendaire de Paris, pas celui d'UTC", () => {
    expect(jourParis(new Date("2026-10-06T22:30:00Z"))).toBe("2026-10-07");
    expect(jourParis(new Date("2026-10-06T21:30:00Z"))).toBe("2026-10-06");
  });
});

describe("fraicheur", () => {
  const maintenant = new Date("2026-10-07T10:00:00Z");

  it("7 jours de retard est encore dans la cible, 8 ne l'est plus", () => {
    const a7 = [ligne("rne", { date_donnees: "2026-09-30" }), ligne("sirene", { date_donnees: "2026-10-06" })];
    expect(fraicheur(a7, maintenant)).toEqual({ etat: "a_jour", jours: 7 });
    const a8 = [ligne("rne", { date_donnees: "2026-10-06" }), ligne("sirene", { date_donnees: "2026-09-29" })];
    expect(fraicheur(a8, maintenant)).toEqual({ etat: "perimee", jours: 8 });
  });

  it("compte en jours de Paris juste après minuit", () => {
    const lignes = [ligne("rne", { date_donnees: "2026-09-30" }), ligne("sirene", { date_donnees: "2026-09-30" })];
    // 22:30 UTC le 06/10 = 00:30 le 07/10 à Paris : 7 jours.
    expect(fraicheur(lignes, new Date("2026-10-06T22:30:00Z"))).toEqual({ etat: "a_jour", jours: 7 });
    // 22:30 UTC le 07/10 = 00:30 le 08/10 à Paris : 8 jours.
    expect(fraicheur(lignes, new Date("2026-10-07T22:30:00Z"))).toEqual({ etat: "perimee", jours: 8 });
  });

  it("est inconnue si une source manque ou n'a pas de date", () => {
    expect(fraicheur([ligne("rne")], maintenant)).toEqual({ etat: "inconnue" });
    expect(fraicheur([], maintenant)).toEqual({ etat: "inconnue" });
    expect(fraicheur([ligne("rne"), ligne("sirene", { date_donnees: null })], maintenant)).toEqual({
      etat: "inconnue",
    });
  });
});

describe("formatVolumes", () => {
  it("garde les clés connues, au format français, et ignore le reste", () => {
    const v = formatVolumes({ jours: 2, fiches: 12345, inconnue: 9, liens_ouverts: "3", pages: null });
    expect(v).toEqual([
      { libelle: "Jours appliqués", valeur: "2" },
      { libelle: "Fiches appliquées", valeur: "12 345" },
    ]);
  });

  it("rend une liste vide pour un volume absent ou mal formé", () => {
    expect(formatVolumes(null)).toEqual([]);
    expect(formatVolumes(undefined)).toEqual([]);
    expect(formatVolumes([1, 2])).toEqual([]);
    expect(formatVolumes("x")).toEqual([]);
  });
});

describe("etatsAffiches", () => {
  it("rend toujours les deux sources, même sans ligne", () => {
    const e = etatsAffiches([ligne("sirene")]);
    expect(e.map((x) => x.code)).toEqual(["rne", "sirene"]);
    expect(e[0].statut.texte).toBe("Jamais synchronisé");
    expect(e[0].dateDonnees).toBeNull();
    expect(e[1].statut.texte).toBe("À jour");
  });

  it("porte la cause d'un échec, et un texte de repli si elle manque", () => {
    const [rne, sirene] = etatsAffiches([
      ligne("rne", { statut: "echec", erreur: "registre introuvable" }),
      ligne("sirene", { statut: "echec", erreur: "  " }),
    ]);
    expect(rne.erreur).toBe("registre introuvable");
    expect(sirene.erreur).toBe("Cause non enregistrée par la synchro.");
  });

  it("n'affiche pas d'erreur hors échec", () => {
    const [rne] = etatsAffiches([ligne("rne", { statut: "succes", erreur: "ancienne erreur" })]);
    expect(rne.erreur).toBeNull();
  });
});
