// C2 et C4 : la logique des Server Actions de reglages/actions.ts, avec un
// dépôt en mémoire qui imite la base (RLS par organisation, unicité du
// numéro de version, version validée figée).
import { describe, expect, it } from "vitest";

import { empreinte } from "./empreinte";
import {
  type Depot,
  type Groupe,
  MESSAGES,
  type Saisie,
  type Version,
  enregistrerBrouillonAvec,
  lignes,
  peutEnregistrer,
  peutValider,
  validerAvec,
} from "./operations";
import type { Reglages } from "./schema";

const CLE = "cle-de-test-FAKE";
const MOI = "00000000-0000-4000-8000-000000000001";
const AUTRE = "00000000-0000-4000-8000-000000000002";
const ORG_A = "org-a";
const ORG_B = "org-b";

type Ligne = Version & {
  groupeId: string;
  organisationId: string;
  creePar: string | null;
  validePar: string | null;
};

function base(organisationDuLecteur: string) {
  const groupes: Groupe[] = [
    { id: "g-a", organisationId: ORG_A, teteSiren: "123456789", nom: "Groupe Fictif" },
    { id: "g-b", organisationId: ORG_B, teteSiren: "987654321", nom: "Autre Groupe" },
  ];
  const reglages: Ligne[] = [
    {
      id: "r-a-1",
      groupeId: "g-a",
      organisationId: ORG_A,
      version: 1,
      contenu: {
        groupe: "Groupe Fictif",
        tete: "123456789",
        marques_sures: ["Marque Fictive"],
        familles_exclues_empreintes: [empreinte("Dupont", CLE)],
      },
      valideLe: "2026-10-06T10:00:00.000Z",
      creePar: null,
      validePar: null,
    },
  ];
  let conflitAuProchainInsert = false;
  const depot: Depot = {
    // RLS : un groupe d'une autre organisation n'est pas lisible.
    async lireGroupe(id) {
      return groupes.find((g) => g.id === id && g.organisationId === organisationDuLecteur) ?? null;
    },
    async derniereVersion(groupeId) {
      const v = reglages.filter((r) => r.groupeId === groupeId).sort((a, b) => b.version - a.version)[0];
      return v ?? null;
    },
    async insererVersion(l) {
      if (conflitAuProchainInsert || reglages.some((r) => r.groupeId === l.groupeId && r.version === l.version)) {
        conflitAuProchainInsert = false;
        return "conflit";
      }
      reglages.push({
        id: `r-${l.groupeId}-${l.version}`,
        groupeId: l.groupeId,
        organisationId: l.organisationId,
        version: l.version,
        contenu: l.contenu,
        valideLe: null,
        creePar: l.creePar,
        validePar: null,
      });
      return "ok";
    },
    async marquerValidee(id, par, le) {
      const r = reglages.find((x) => x.id === id);
      if (!r || r.valideLe) return false;
      r.valideLe = le;
      r.validePar = par;
      return true;
    },
  };
  return {
    depot,
    reglages,
    simulerCourse: () => {
      conflitAuProchainInsert = true;
    },
  };
}

function saisie(sur: Partial<Saisie> = {}, listes: Partial<Saisie["listes"]> = {}): Saisie {
  return {
    groupeId: "g-a",
    baseVersion: 1,
    famillesAjoutees: "",
    retirerFamilles: false,
    ...sur,
    listes: {
      marques_sures: "Marque Fictive\nNouvelle Marque",
      marques_ambigues: "",
      marques_sures_homonymes: "",
      marques_sigles: "",
      organigramme: "",
      exclus: "",
      exclus_noms: "",
      priorite: "",
      ...listes,
    },
  };
}

describe("peutEnregistrer et peutValider", () => {
  it("n'enregistre que sur la dernière version ouverte", () => {
    expect(peutEnregistrer(3, 3)).toBe(true);
    expect(peutEnregistrer(4, 3)).toBe(false);
    expect(peutEnregistrer(null, 0)).toBe(true);
    expect(peutEnregistrer(null, 1)).toBe(false);
  });

  it("ne valide que la dernière version, en brouillon", () => {
    expect(peutValider({ version: 2, valideLe: null }, 2)).toBe("ok");
    expect(peutValider({ version: 3, valideLe: null }, 2)).toBe("pas_la_derniere");
    expect(peutValider({ version: 2, valideLe: "2026-10-07" }, 2)).toBe("deja_validee");
    expect(peutValider(null, 1)).toBe("aucune");
  });
});

describe("lignes", () => {
  it("retire blancs, lignes vides et doublons, garde l'ordre", () => {
    expect(lignes("  B \r\n\nA\nB\n  ")).toEqual(["B", "A"]);
    expect(lignes("")).toEqual([]);
  });
});

describe("enregistrerBrouillonAvec", () => {
  it("crée la version suivante, en brouillon, avec son auteur (C4)", async () => {
    const { depot, reglages } = base(ORG_A);
    const r = await enregistrerBrouillonAvec(depot, MOI, saisie(), CLE);
    expect(r).toMatchObject({ statut: "ok", version: 2 });
    const v2 = reglages.find((x) => x.version === 2)!;
    expect(v2.creePar).toBe(MOI);
    expect(v2.valideLe).toBeNull();
    expect(v2.contenu.marques_sures).toEqual(["Marque Fictive", "Nouvelle Marque"]);
    // Groupe et tête viennent du groupe, pas de la saisie.
    expect(v2.contenu).toMatchObject({ groupe: "Groupe Fictif", tete: "123456789" });
    // Les empreintes existantes sont reprises de la base.
    expect(v2.contenu.familles_exclues_empreintes).toEqual([empreinte("Dupont", CLE)]);
  });

  it("refuse si une autre version a été enregistrée depuis l'ouverture (C2)", async () => {
    const { depot, reglages } = base(ORG_A);
    expect(await enregistrerBrouillonAvec(depot, AUTRE, saisie(), CLE)).toMatchObject({ statut: "ok" });
    // Deuxième consultant, ouvert sur la version 1.
    const r = await enregistrerBrouillonAvec(depot, MOI, saisie({}, { marques_sures: "Autre" }), CLE);
    expect(r).toEqual({ statut: "erreur", message: MESSAGES.versionChangee });
    expect(reglages).toHaveLength(2);
  });

  it("refuse sur une course au même numéro, sans réessayer par-dessus", async () => {
    const { depot, reglages, simulerCourse } = base(ORG_A);
    simulerCourse();
    const r = await enregistrerBrouillonAvec(depot, MOI, saisie(), CLE);
    expect(r).toEqual({ statut: "erreur", message: MESSAGES.versionChangee });
    expect(reglages).toHaveLength(1);
  });

  it("refuse un groupe d'une autre organisation", async () => {
    const { depot, reglages } = base(ORG_A);
    const r = await enregistrerBrouillonAvec(depot, MOI, saisie({ groupeId: "g-b" }), CLE);
    expect(r).toEqual({ statut: "erreur", message: MESSAGES.groupeIntrouvable });
    expect(reglages).toHaveLength(1);
  });

  it("ajoute une famille par son empreinte, jamais par son nom", async () => {
    const { depot, reglages } = base(ORG_A);
    const r = await enregistrerBrouillonAvec(
      depot,
      MOI,
      saisie({ famillesAjoutees: "Nom Zorglub\n  dupont " }),
      CLE,
    );
    expect(r.statut).toBe("ok");
    expect(JSON.stringify(r)).not.toMatch(/zorglub|dupont/i);
    const v2 = reglages.find((x) => x.version === 2)!;
    // Dupont était déjà exclu : pas de doublon.
    expect(v2.contenu.familles_exclues_empreintes).toEqual([
      empreinte("Dupont", CLE),
      empreinte("NOM ZORGLUB", CLE),
    ]);
    expect(JSON.stringify(v2.contenu)).not.toMatch(/zorglub|dupont/i);
  });

  it("retire toutes les familles", async () => {
    const { depot, reglages } = base(ORG_A);
    await enregistrerBrouillonAvec(depot, MOI, saisie({ retirerFamilles: true }), CLE);
    expect(reglages.find((x) => x.version === 2)!.contenu.familles_exclues_empreintes).toEqual([]);
  });

  it("refuse d'ajouter une famille sans clé d'empreinte", async () => {
    const { depot, reglages } = base(ORG_A);
    const r = await enregistrerBrouillonAvec(depot, MOI, saisie({ famillesAjoutees: "Nom Fictif" }), null);
    expect(r).toEqual({ statut: "erreur", message: MESSAGES.cleManquante });
    expect(reglages).toHaveLength(1);
  });

  it("enregistre sans clé quand aucune famille n'est ajoutée", async () => {
    const { depot } = base(ORG_A);
    expect(await enregistrerBrouillonAvec(depot, MOI, saisie(), null)).toMatchObject({ statut: "ok" });
  });

  it("refuse une saisie invalide, en français", async () => {
    const { depot, reglages } = base(ORG_A);
    const r = await enregistrerBrouillonAvec(depot, MOI, saisie({}, { exclus: "775 670 417\n12345" }), CLE);
    expect(r).toEqual({ statut: "erreur", message: "SIREN exclus, valeur n° 2 : un SIREN fait 9 chiffres." });
    expect(reglages).toHaveLength(1);
  });

  it("accepte un SIREN écrit avec des espaces", async () => {
    const { depot, reglages } = base(ORG_A);
    await enregistrerBrouillonAvec(depot, MOI, saisie({}, { exclus: "775 670 417" }), CLE);
    expect(reglages.find((x) => x.version === 2)!.contenu.exclus).toEqual(["775670417"]);
  });

  it("ne crée pas de version si rien n'a changé", async () => {
    const { depot, reglages } = base(ORG_A);
    const r = await enregistrerBrouillonAvec(depot, MOI, saisie({}, { marques_sures: "Marque Fictive" }), CLE);
    expect(r).toEqual({ statut: "erreur", message: MESSAGES.rienNaChange });
    expect(reglages).toHaveLength(1);
  });

  it("crée la version 1 d'un groupe neuf", async () => {
    const { depot, reglages } = base(ORG_A);
    reglages.length = 0;
    const r = await enregistrerBrouillonAvec(depot, MOI, saisie({ baseVersion: 0 }), CLE);
    expect(r).toMatchObject({ statut: "ok", version: 1 });
  });
});

describe("validerAvec", () => {
  const maintenant = () => new Date("2026-10-07T12:00:00.000Z");

  it("valide la dernière version, avec validateur et date (C4)", async () => {
    const { depot, reglages } = base(ORG_A);
    await enregistrerBrouillonAvec(depot, AUTRE, saisie(), CLE);
    const r = await validerAvec(depot, MOI, { groupeId: "g-a", version: 2 }, maintenant);
    expect(r).toMatchObject({ statut: "ok", version: 2 });
    const v2 = reglages.find((x) => x.version === 2)!;
    expect(v2).toMatchObject({ creePar: AUTRE, validePar: MOI, valideLe: "2026-10-07T12:00:00.000Z" });
  });

  it("refuse une validation qui ne part pas de la dernière version (C2)", async () => {
    const { depot, reglages } = base(ORG_A);
    await enregistrerBrouillonAvec(depot, MOI, saisie(), CLE);
    await enregistrerBrouillonAvec(depot, AUTRE, saisie({ baseVersion: 2 }, { marques_sures: "X" }), CLE);
    const r = await validerAvec(depot, MOI, { groupeId: "g-a", version: 2 }, maintenant);
    expect(r).toEqual({ statut: "erreur", message: MESSAGES.versionChangee });
    expect(reglages.find((x) => x.version === 2)!.valideLe).toBeNull();
  });

  it("refuse une version déjà validée", async () => {
    const { depot } = base(ORG_A);
    expect(await validerAvec(depot, MOI, { groupeId: "g-a", version: 1 })).toEqual({
      statut: "erreur",
      message: MESSAGES.dejaValidee,
    });
  });

  it("refuse si la version a été validée entre-temps", async () => {
    const { depot, reglages } = base(ORG_A);
    await enregistrerBrouillonAvec(depot, MOI, saisie(), CLE);
    const marquer = depot.marquerValidee;
    depot.marquerValidee = async (id, par, le) => {
      reglages.find((x) => x.id === id)!.valideLe = "2026-10-07T11:59:00.000Z";
      return marquer(id, par, le);
    };
    expect(await validerAvec(depot, MOI, { groupeId: "g-a", version: 2 })).toEqual({
      statut: "erreur",
      message: MESSAGES.dejaValidee,
    });
  });

  it("refuse un groupe d'une autre organisation", async () => {
    const { depot } = base(ORG_B);
    expect(await validerAvec(depot, MOI, { groupeId: "g-a", version: 1 })).toEqual({
      statut: "erreur",
      message: MESSAGES.groupeIntrouvable,
    });
  });

  it("refuse un groupe sans réglages", async () => {
    const { depot, reglages } = base(ORG_A);
    reglages.length = 0;
    expect(await validerAvec(depot, MOI, { groupeId: "g-a", version: 1 })).toEqual({
      statut: "erreur",
      message: MESSAGES.rienAValider,
    });
  });

  it("ne valide pas un contenu mal formé", async () => {
    const { depot, reglages } = base(ORG_A);
    reglages.push({
      ...reglages[0],
      id: "r-a-2",
      version: 2,
      valideLe: null,
      contenu: { groupe: "Groupe Fictif", tete: "123" } as Reglages,
    });
    const r = await validerAvec(depot, MOI, { groupeId: "g-a", version: 2 });
    expect(r.statut).toBe("erreur");
    expect(reglages[1].valideLe).toBeNull();
  });
});
