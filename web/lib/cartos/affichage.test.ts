// Affichage des cartos (T021) : statuts en français, durée, date des données,
// et ce qui permet ou empêche un lancement.
import { describe, expect, it } from "vitest";

import {
  LIBELLE_STATUT,
  MESSAGES,
  ORPHELINE_APRES_MS,
  STATUTS,
  bloquante,
  dateDonneesFr,
  dureeFr,
  effetFr,
  estActive,
  libelleStatut,
  peutLancer,
} from "./affichage";

describe("statuts", () => {
  it("chaque statut de la base a un libellé français", () => {
    expect(STATUTS.map((s) => LIBELLE_STATUT[s])).toEqual(["En attente", "En cours", "Terminée", "Échec"]);
  });

  it("un statut inconnu n'affiche jamais la valeur brute", () => {
    expect(libelleStatut("running")).toBe("Statut inconnu");
  });

  it("seules en attente et en cours sont actives", () => {
    expect(STATUTS.filter(estActive)).toEqual(["en_attente", "en_cours"]);
  });
});

describe("bloquante", () => {
  const maintenant = Date.parse("2026-10-07T12:00:00Z");
  const il_y_a = (ms: number) => new Date(maintenant - ms).toISOString();

  it("une carto active bloque un nouveau lancement", () => {
    expect(bloquante({ statut: "en_cours", travail_id: 3, cree_le: il_y_a(60 * 60_000) }, maintenant)).toBe(true);
    expect(bloquante({ statut: "en_attente", travail_id: 3, cree_le: il_y_a(60 * 60_000) }, maintenant)).toBe(true);
    expect(bloquante({ statut: "en_attente", travail_id: null, cree_le: il_y_a(1000) }, maintenant)).toBe(true);
  });

  it("une carto finie ne bloque pas", () => {
    expect(bloquante({ statut: "terminee", travail_id: 3, cree_le: il_y_a(1000) }, maintenant)).toBe(false);
    expect(bloquante({ statut: "echec", travail_id: 3, cree_le: il_y_a(1000) }, maintenant)).toBe(false);
  });

  it("une carto en attente sans travail depuis plus de 10 min est orpheline", () => {
    const vieille = il_y_a(ORPHELINE_APRES_MS + 1);
    expect(bloquante({ statut: "en_attente", travail_id: null, cree_le: vieille }, maintenant)).toBe(false);
    // Avec un travail, elle attend dans la file : elle bloque toujours.
    expect(bloquante({ statut: "en_attente", travail_id: 9, cree_le: vieille }, maintenant)).toBe(true);
  });
});

describe("peutLancer", () => {
  it("sans version enregistrée, refus avec l'explication", () => {
    expect(peutLancer({ version: false, cartoActive: false })).toEqual({
      ok: false,
      message: MESSAGES.aucuneVersion,
    });
  });

  it("une carto déjà active empêche un second lancement", () => {
    expect(peutLancer({ version: true, cartoActive: true })).toEqual({
      ok: false,
      message: MESSAGES.dejaEnCours,
    });
  });

  it("version enregistrée et rien en cours : on peut lancer", () => {
    expect(peutLancer({ version: true, cartoActive: false })).toEqual({ ok: true });
  });

  it("les messages sont en français et disent quoi faire", () => {
    expect(MESSAGES.aucuneVersion).toMatch(/enregistrez-les/);
    expect(MESSAGES.aucuneVersion).not.toMatch(/valid/i);
    expect(MESSAGES.dejaEnCours).toMatch(/Attendez/);
  });
});

describe("dureeFr", () => {
  it.each([
    [null, "—"],
    [undefined, "—"],
    [-1, "—"],
    [0, "0 ms"],
    [850, "850 ms"],
    [1000, "1 s"],
    [12_400, "12 s"],
    [59_499, "59 s"],
    [59_500, "1 min 00 s"],
    [64_000, "1 min 04 s"],
    [312_000, "5 min 12 s"],
  ])("%s ms → %s", (ms, attendu) => {
    expect(dureeFr(ms)).toBe(attendu);
  });
});

describe("dateDonneesFr", () => {
  it("une date Postgres s'écrit à la française, sans décalage de fuseau", () => {
    expect(dateDonneesFr("2026-03-04")).toBe("04/03/2026");
    expect(dateDonneesFr("2026-12-31")).toBe("31/12/2026");
  });

  it("vide ou illisible : un tiret", () => {
    expect(dateDonneesFr(null)).toBe("—");
    expect(dateDonneesFr("04/03/2026")).toBe("—");
  });
});

describe("effetFr (T051, C2)", () => {
  it("n'affiche rien quand l'effet n'est pas mesuré : jamais un faux zéro", () => {
    expect(effetFr(null, null)).toBeNull();
    expect(effetFr(undefined, 3)).toBeNull();
    expect(effetFr(4, null)).toBeNull();
  });

  it("dit qu'il n'y a aucune différence", () => {
    expect(effetFr(0, 0)).toBe("Les corrections n'ajoutent ni ne retirent aucune société.");
  });

  it("accorde le singulier et le pluriel, en français", () => {
    expect(effetFr(1, 1)).toBe("1 société ajoutée, 1 retirée par rapport à la carto sans correction.");
    expect(effetFr(12, 3)).toBe("12 sociétés ajoutées, 3 retirées par rapport à la carto sans correction.");
    expect(effetFr(0, 2)).toBe("Aucune société ajoutée, 2 retirées par rapport à la carto sans correction.");
    expect(effetFr(5, 0)).toBe("5 sociétés ajoutées, aucune retirée par rapport à la carto sans correction.");
  });

  it("sépare les milliers à la française", () => {
    expect(effetFr(1234, 0)).toMatch(/^1\s234 sociétés ajoutées/);
  });
});
