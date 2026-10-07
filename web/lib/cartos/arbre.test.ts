import { describe, expect, it } from "vitest";

import {
  INCONNU,
  type SocieteCarto,
  compter,
  construireArbre,
  libelleConfiance,
  parents,
  sirenFr,
  visibles,
} from "./arbre";

const societe = (siren: string, champs: Partial<SocieteCarto> = {}): SocieteCarto => ({
  siren,
  nom: `Société ${siren}`,
  niveau: 1,
  maison_mere_siren: "100000000",
  confiance: "A",
  preuve: "président au registre",
  ciblable: true,
  raison_ciblable: "société active",
  opposition_prospection: false,
  non_diffusible: false,
  ...champs,
});

const tete = societe("100000000", { nom: "Tête", niveau: 0, maison_mere_siren: null, confiance: null });

describe("construireArbre", () => {
  it("une carto réduite à la tête : une seule racine, sans enfant", () => {
    const [racine, ...reste] = construireArbre([tete]);
    expect(reste).toEqual([]);
    expect(racine.id).toBe("100000000");
    expect(racine.enfants).toEqual([]);
    expect(racine.descendants).toBe(0);
    expect(racine.maisonMere).toBeNull();
  });

  it("range chaque société sous sa maison mère et compte les descendants", () => {
    const racines = construireArbre([
      societe("300000000", { nom: "Petite-fille", niveau: 2, maison_mere_siren: "200000000" }),
      societe("200000000", { nom: "Fille" }),
      tete,
    ]);
    expect(racines).toHaveLength(1);
    const [fille] = racines[0].enfants;
    expect(fille.id).toBe("200000000");
    expect(fille.maisonMere).toEqual({ siren: "100000000", nom: "Tête" });
    expect(fille.enfants.map((e) => e.id)).toEqual(["300000000"]);
    expect(racines[0].descendants).toBe(2);
    expect(fille.descendants).toBe(1);
  });

  it("trie les enfants par nom, sans tenir compte de la casse ni des accents, puis par SIREN", () => {
    const racines = construireArbre([
      tete,
      societe("400000000", { nom: "zèbre" }),
      societe("300000000", { nom: "Écureuil" }),
      societe("200000000", { nom: "ecureuil" }),
      societe("500000000", { nom: null }),
      societe("600000000", { nom: "Abeille" }),
    ]);
    expect(racines[0].enfants.map((e) => e.id)).toEqual([
      "600000000",
      "200000000",
      "300000000",
      "400000000",
      "500000000",
    ]);
  });

  it("une société dont la maison mère n'est pas dans la carto va sous « Rattachement inconnu », jamais perdue", () => {
    const racines = construireArbre([
      tete,
      societe("200000000", { maison_mere_siren: "999999999" }),
      societe("300000000", { maison_mere_siren: "200000000", niveau: 2 }),
    ]);
    expect(racines.map((r) => r.id)).toEqual(["100000000", INCONNU]);
    const inconnu = racines[1];
    expect(inconnu.societe).toBeNull();
    expect(inconnu.enfants.map((e) => e.id)).toEqual(["200000000"]);
    expect(inconnu.enfants[0].maisonMere).toBeNull();
    expect(inconnu.enfants[0].enfants.map((e) => e.id)).toEqual(["300000000"]);
    expect(inconnu.descendants).toBe(2);
  });

  it("une boucle de maisons mères ne fait ni perdre ni répéter une société", () => {
    const racines = construireArbre([
      tete,
      societe("200000000", { maison_mere_siren: "300000000" }),
      societe("300000000", { maison_mere_siren: "200000000" }),
    ]);
    const ids = visibles(racines, new Set(parents(racines))).map((v) => v.noeud.id);
    expect(ids.filter((id) => id !== INCONNU).sort()).toEqual(["100000000", "200000000", "300000000"]);
  });

  it("une liste vide donne un arbre vide", () => {
    expect(construireArbre([])).toEqual([]);
  });
});

describe("visibles", () => {
  const racines = construireArbre([
    tete,
    societe("200000000", { nom: "B" }),
    societe("210000000", { nom: "B1", maison_mere_siren: "200000000", niveau: 2 }),
    societe("300000000", { nom: "C" }),
  ]);

  it("ne montre pas les enfants d'un nœud replié", () => {
    expect(visibles(racines, new Set()).map((v) => v.noeud.id)).toEqual(["100000000"]);
  });

  it("suit l'ordre de lecture et donne le parent de chacun", () => {
    const tout = visibles(racines, new Set(parents(racines)));
    expect(tout.map((v) => [v.noeud.id, v.parent])).toEqual([
      ["100000000", null],
      ["200000000", "100000000"],
      ["210000000", "200000000"],
      ["300000000", "100000000"],
    ]);
  });
});

describe("libellés", () => {
  it("écrit la confiance en toutes lettres", () => {
    expect(libelleConfiance("A")).toBe("A — lu au registre");
    expect(libelleConfiance("B")).toBe("B — au moins deux indices");
    expect(libelleConfiance("C")).toBe("C — à vérifier");
    expect(libelleConfiance(null)).toBe("Tête du groupe");
  });

  it("groupe le SIREN par trois chiffres", () => {
    expect(sirenFr("552120222")).toBe("552 120 222");
    expect(sirenFr("12")).toBe("12");
  });

  it("compte les sociétés ciblables, opposées et non diffusibles", () => {
    expect(
      compter([
        tete,
        societe("200000000", { ciblable: false, opposition_prospection: true }),
        societe("300000000", { non_diffusible: true }),
      ]),
    ).toEqual({ societes: 3, ciblables: 2, opposees: 1, nonDiffusibles: 1 });
  });
});
