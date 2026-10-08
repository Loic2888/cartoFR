// T026 : la revue d'une proposition de l'IA et le comptage des corrections
// (C2, SC-007), avec un dépôt en mémoire qui imite la base (RLS par
// organisation, unicité du numéro de version).
import { describe, expect, it } from "vitest";

import type { Groupe } from "./operations";
import {
  type Ajout,
  type Decision,
  type DepotProposition,
  type Element,
  MESSAGES_PROPOSITION,
  type TravailProposition,
  type VersionProposee,
  appliquerRevue,
  demanderPropositionAvec,
  etatTravail,
  lireElements,
  sourceSure,
  validerPropositionAvec,
} from "./proposition";
import type { Reglages } from "./schema";

const MOI = "00000000-0000-4000-8000-000000000001";
const SOURCE = "https://groupe-fictif.example/marques";

const IA = { origine: "ia", deja_valide_en: null } as const;
const ELEMENTS: Element[] = [
  { ...IA, liste: "marques_sures", valeur: "Marque Fictive", source: SOURCE, homonymes: 0 },
  { ...IA, liste: "marques_ambigues", valeur: "Soleil", source: SOURCE, homonymes: 12 },
  { ...IA, liste: "marques_sigles", valeur: "GFX", source: SOURCE, homonymes: null },
  { ...IA, liste: "organigramme", valeur: "Maison Fictive SAS", source: SOURCE },
  { ...IA, liste: "exclus_noms", valeur: "Fictif Holding", source: SOURCE },
];

const CONTENU: Reglages = {
  groupe: "Groupe Fictif",
  tete: "123456789",
  marques_sures: ["Marque Fictive"],
  marques_ambigues: ["Soleil"],
  marques_sigles: ["GFX"],
  organigramme: ["Maison Fictive SAS"],
  exclus_noms: ["Fictif Holding"],
  exclus: ["987654321"],
  familles_exclues_empreintes: ["a".repeat(64)],
};

const tout = (choix: "accepter" | "rejeter"): Decision[] => ELEMENTS.map(() => ({ choix }));

describe("appliquerRevue", () => {
  it("tout garder : aucune correction, contenu inchangé", () => {
    const r = appliquerRevue(CONTENU, ELEMENTS, tout("accepter"), []);
    expect(r).toEqual({ ok: true, corrections: 0, contenu: CONTENU });
  });

  it("chaque rejet, correction réelle et ajout compte pour une correction", () => {
    const decisions: Decision[] = [
      { choix: "rejeter" },
      { choix: "corriger", valeur: "Soleil", liste: "marques_sures" }, // change de liste : 1
      { choix: "corriger", valeur: " GFX ", liste: "marques_sigles" }, // rien ne change : 0
      { choix: "corriger", valeur: "Maison Fictive", liste: "organigramme" }, // valeur : 1
      { choix: "accepter" },
    ];
    const ajouts: Ajout[] = [
      { liste: "marques_sures", valeur: "Autre Marque\nTroisième Marque" },
      { liste: "marques_sures", valeur: "Autre Marque" }, // doublon : compté une fois
    ];
    const r = appliquerRevue(CONTENU, ELEMENTS, decisions, ajouts);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.corrections).toBe(5);
    expect(r.contenu.marques_sures).toEqual(["Soleil", "Autre Marque", "Troisième Marque"]);
    expect(r.contenu.marques_ambigues).toEqual([]);
    expect(r.contenu.marques_sigles).toEqual(["GFX"]);
    expect(r.contenu.organigramme).toEqual(["Maison Fictive"]);
    // Les clés que l'IA ne propose pas restent.
    expect(r.contenu.exclus).toEqual(["987654321"]);
    expect(r.contenu.familles_exclues_empreintes).toEqual(["a".repeat(64)]);
  });

  it("tout rejeter : autant de corrections que d'éléments", () => {
    const r = appliquerRevue(CONTENU, ELEMENTS, tout("rejeter"), []);
    expect(r.ok && r.corrections).toBe(ELEMENTS.length);
  });

  it("refuse une valeur corrigée vide et une revue qui ne correspond plus", () => {
    const vide: Decision[] = [{ choix: "corriger", valeur: "  ", liste: "marques_sures" }, ...tout("accepter").slice(1)];
    expect(appliquerRevue(CONTENU, ELEMENTS, vide, []).ok).toBe(false);
    expect(appliquerRevue(CONTENU, ELEMENTS, tout("accepter").slice(1), []).ok).toBe(false);
  });

  it("proposition vide : seuls les ajouts comptent", () => {
    const r = appliquerRevue(CONTENU, [], [], [{ liste: "organigramme", valeur: "Maison Fictive SAS" }]);
    expect(r.ok && r.corrections).toBe(1);
  });
});

describe("éléments déjà validés (principe 2)", () => {
  // La proposition reprend une marque validée que l'IA n'a pas reproposée, et
  // une autre que l'IA repropose dans une autre liste (rangement : worker).
  const VALIDEE: Element = {
    liste: "marques_sures",
    valeur: "Marque Validée",
    source: null,
    origine: "validee",
    deja_valide_en: "marques_sures",
  };
  const REPROPOSEE: Element = { ...ELEMENTS[1], deja_valide_en: "marques_sures" };
  const elements = [ELEMENTS[0], REPROPOSEE, VALIDEE];
  const contenu = { ...CONTENU, marques_sures: ["Marque Fictive", "Marque Validée"], marques_ambigues: ["Soleil"] };
  const garder: Decision[] = elements.map(() => ({ choix: "accepter" }));

  it("gardé par défaut : rien n'est perdu, aucune correction", () => {
    const r = appliquerRevue(contenu, elements, garder, []);
    expect(r.ok && r.corrections).toBe(0);
    expect(r.ok && r.contenu.marques_sures).toEqual(["Marque Fictive", "Marque Validée"]);
    expect(r.ok && r.contenu.marques_ambigues).toEqual(["Soleil"]);
  });

  it("rejeter ou modifier un élément déjà validé n'est pas une correction de l'IA", () => {
    const rejet = appliquerRevue(contenu, elements, [garder[0], garder[1], { choix: "rejeter" }], []);
    expect(rejet.ok && rejet.corrections).toBe(0);
    expect(rejet.ok && rejet.contenu.marques_sures).toEqual(["Marque Fictive"]);
    const modif = appliquerRevue(
      contenu,
      elements,
      [garder[0], garder[1], { choix: "corriger", valeur: "Autre", liste: "marques_ambigues" }],
      [],
    );
    expect(modif.ok && modif.corrections).toBe(0);
    expect(modif.ok && modif.contenu.marques_ambigues).toEqual(["Soleil", "Autre"]);
  });

  it("un élément de l'IA reproposé d'une valeur validée compte comme les autres", () => {
    const r = appliquerRevue(contenu, elements, [garder[0], { choix: "rejeter" }, garder[2]], []);
    expect(r.ok && r.corrections).toBe(1);
  });

  it("lit une proposition sans origine (ancienne forme) comme venant de l'IA", () => {
    const lus = lireElements({ modele: "m", elements: [{ liste: "marques_sures", valeur: "X", source: SOURCE }] });
    expect(lus?.[0]).toMatchObject({ origine: "ia", deja_valide_en: null });
    expect(lireElements({ modele: "m", elements: [VALIDEE] })).toEqual([VALIDEE]);
  });
});

describe("lecture et affichage", () => {
  it("lit les éléments d'une proposition, refuse une forme inattendue", () => {
    expect(lireElements({ modele: "m", elements: ELEMENTS })).toEqual(ELEMENTS);
    expect(lireElements({ modele: "m", elements: [{ liste: "exclus", valeur: "x", source: SOURCE }] })).toBeNull();
    expect(lireElements(null)).toBeNull();
  });

  it("une source n'est un lien qu'en http(s)", () => {
    expect(sourceSure(SOURCE)).toBe(SOURCE);
    expect(sourceSure("javascript:alert(1)")).toBeNull();
    expect(sourceSure("pas une url")).toBeNull();
    expect(sourceSure(null)).toBeNull();
  });

  it("traduit l'état du dernier travail", () => {
    const t = (statut: TravailProposition["statut"], erreur: string | null = null): TravailProposition => ({
      statut,
      erreur,
      creeLe: "2026-10-08T10:00:00+00:00",
    });
    expect(etatTravail(null, null)).toBeNull();
    expect(etatTravail(t("en_cours"), null)).toMatch(/prépare/);
    expect(etatTravail(t("termine"), null)).toBeNull();
    expect(etatTravail(t("echec", "échec du travail (CleIaManquante)"), null)).toMatch(/clé/);
    expect(etatTravail(t("echec"), "2026-10-08T09:00:00+00:00")).toMatch(/échoué/);
    // Un échec plus ancien que la dernière version ne s'affiche plus.
    expect(etatTravail(t("echec"), "2026-10-08T11:00:00+00:00")).toBeNull();
  });
});

type Ligne = VersionProposee & { groupeId: string; organisationId: string; corrections: number | null; propositionId: string | null; validePar: string | null };

function base(organisationDuLecteur: string) {
  const groupes: Groupe[] = [
    { id: "g-a", organisationId: "org-a", teteSiren: "123456789", nom: "Groupe Fictif" },
    { id: "g-b", organisationId: "org-b", teteSiren: "987654321", nom: "Autre Groupe" },
  ];
  const reglages: Ligne[] = [
    {
      id: "r-a-2",
      groupeId: "g-a",
      organisationId: "org-a",
      version: 2,
      origine: "proposition",
      contenu: CONTENU,
      proposition: { modele: "modele-test", elements: ELEMENTS },
      valideLe: null,
      corrections: null,
      propositionId: null,
      validePar: null,
    },
  ];
  const travaux: (TravailProposition & { groupeId: string; organisationId: string })[] = [];
  const depot: DepotProposition = {
    async lireGroupe(id) {
      return groupes.find((g) => g.id === id && g.organisationId === organisationDuLecteur) ?? null;
    },
    async derniereVersion(groupeId) {
      const lignes = reglages.filter((r) => r.groupeId === groupeId).sort((a, b) => b.version - a.version);
      return lignes[0] ?? null;
    },
    async dernierTravail(groupeId) {
      return travaux.filter((t) => t.groupeId === groupeId).at(-1) ?? null;
    },
    async insererTravail(ligne) {
      travaux.push({ ...ligne, statut: "en_attente", erreur: null, creeLe: new Date().toISOString() });
      return "ok";
    },
    async insererVersionValidee(ligne) {
      if (reglages.some((r) => r.groupeId === ligne.groupeId && r.version === ligne.version)) return "conflit";
      reglages.push({
        id: `r-${ligne.version}`,
        groupeId: ligne.groupeId,
        organisationId: ligne.organisationId,
        version: ligne.version,
        origine: "saisie",
        contenu: ligne.contenu,
        proposition: null,
        valideLe: ligne.le,
        corrections: ligne.corrections,
        propositionId: ligne.propositionId,
        validePar: ligne.par,
      });
      return "ok";
    },
  };
  return { depot, reglages, travaux };
}

describe("demanderPropositionAvec", () => {
  it("met un travail en file, une seule fois à la fois", async () => {
    const { depot, travaux } = base("org-a");
    const r = await demanderPropositionAvec(depot, MOI, "g-a");
    expect(r.statut).toBe("ok");
    expect(travaux).toHaveLength(1);
    expect(travaux[0]).toMatchObject({ groupeId: "g-a", organisationId: "org-a", demandePar: MOI });
    const encore = await demanderPropositionAvec(depot, MOI, "g-a");
    expect(encore).toEqual({ statut: "erreur", message: MESSAGES_PROPOSITION.dejaEnCours });
    expect(travaux).toHaveLength(1);
  });

  it("un groupe d'une autre organisation est introuvable", async () => {
    const { depot, travaux } = base("org-b");
    expect((await demanderPropositionAvec(depot, MOI, "g-a")).statut).toBe("erreur");
    expect(travaux).toHaveLength(0);
  });
});

describe("validerPropositionAvec (C2)", () => {
  const le = () => new Date("2026-10-08T12:00:00.000Z");

  it("enregistre une version validée avec son nombre de corrections", async () => {
    const { depot, reglages } = base("org-a");
    const decisions: Decision[] = [{ choix: "rejeter" }, ...tout("accepter").slice(1)];
    const r = await validerPropositionAvec(
      depot,
      MOI,
      { groupeId: "g-a", version: 2, decisions, ajouts: [{ liste: "marques_sures", valeur: "Nouvelle" }] },
      le,
    );
    expect(r).toMatchObject({ statut: "ok", version: 3, corrections: 2 });
    const v3 = reglages.find((x) => x.version === 3);
    expect(v3).toMatchObject({
      origine: "saisie",
      corrections: 2,
      propositionId: "r-a-2",
      valideLe: "2026-10-08T12:00:00.000Z",
      validePar: MOI,
    });
    expect(v3?.contenu.marques_sures).toEqual(["Nouvelle"]);
    // La proposition elle-même reste non validée (principe 1).
    expect(reglages.find((x) => x.version === 2)?.valideLe).toBeNull();
  });

  it("refuse si la dernière version n'est plus la proposition revue", async () => {
    const { depot } = base("org-a");
    const r = await validerPropositionAvec(depot, MOI, { groupeId: "g-a", version: 1, decisions: tout("accepter"), ajouts: [] });
    expect(r.statut).toBe("erreur");
    await validerPropositionAvec(depot, MOI, { groupeId: "g-a", version: 2, decisions: tout("accepter"), ajouts: [] }, le);
    const deux = await validerPropositionAvec(depot, MOI, { groupeId: "g-a", version: 2, decisions: tout("accepter"), ajouts: [] });
    expect(deux).toEqual({ statut: "erreur", message: MESSAGES_PROPOSITION.pasDeProposition });
  });

  it("un groupe d'une autre organisation est introuvable", async () => {
    const { depot, reglages } = base("org-b");
    const r = await validerPropositionAvec(depot, MOI, { groupeId: "g-a", version: 2, decisions: tout("accepter"), ajouts: [] });
    expect(r.statut).toBe("erreur");
    expect(reglages).toHaveLength(1);
  });

  it("une correction qui rend les réglages invalides est refusée", async () => {
    const { depot, reglages } = base("org-a");
    const decisions: Decision[] = [
      { choix: "corriger", valeur: "x".repeat(201), liste: "marques_sures" },
      ...tout("accepter").slice(1),
    ];
    const r = await validerPropositionAvec(depot, MOI, { groupeId: "g-a", version: 2, decisions, ajouts: [] });
    expect(r.statut).toBe("erreur");
    expect(reglages).toHaveLength(1);
  });
});
