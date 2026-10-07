// Lancer une carto (T021) : la logique de cartos/actions.ts, avec un dépôt
// en mémoire qui imite la base (RLS par organisation, cartos et travaux).
import { describe, expect, it } from "vitest";

import { MESSAGES } from "./affichage";
import { type Depot, lancerCartoAvec } from "./operations";

const ORG_A = "org-a";
const ORG_B = "org-b";

type Carto = {
  id: string;
  organisationId: string;
  groupeId: string;
  reglagesId: string;
  statut: string;
  travailId: number | null;
};
type Travail = { id: number; organisationId: string; cartoId: string };

function base(organisationDuLecteur: string, options: { echecTravail?: boolean; concurrent?: boolean } = {}) {
  const groupes = [
    { id: "g-a", organisationId: ORG_A },
    { id: "g-b", organisationId: ORG_B },
    { id: "g-a-brouillon", organisationId: ORG_A },
  ];
  const reglages = [
    { id: "r-a-1", groupeId: "g-a", version: 1, valide: true },
    { id: "r-a-2", groupeId: "g-a", version: 2, valide: true },
    { id: "r-a-3", groupeId: "g-a", version: 3, valide: false },
    { id: "r-b-1", groupeId: "g-b", version: 1, valide: true },
    { id: "r-ab-1", groupeId: "g-a-brouillon", version: 1, valide: false },
  ];
  const cartos: Carto[] = [];
  const travaux: Travail[] = [];
  let n = 0;
  const depot: Depot = {
    async lireGroupe(id) {
      return groupes.find((g) => g.id === id && g.organisationId === organisationDuLecteur) ?? null;
    },
    async derniereVersionValidee(groupeId) {
      const v = reglages
        .filter((r) => r.groupeId === groupeId && r.valide)
        .sort((a, b) => b.version - a.version)[0];
      return v ? { id: v.id, version: v.version } : null;
    },
    async cartosActives(groupeId) {
      return cartos
        .filter((c) => c.groupeId === groupeId && (c.statut === "en_attente" || c.statut === "en_cours"))
        .map((c) => c.id);
    },
    async insererCarto(ligne) {
      const id = `c-${++n}`;
      cartos.push({ id, ...ligne, statut: "en_attente", travailId: null });
      // Un autre membre lance la même carto juste après notre insertion.
      if (options.concurrent) {
        cartos.push({ id: `c-concurrent`, ...ligne, statut: "en_attente", travailId: null });
      }
      return id;
    },
    async supprimerCarto(id) {
      cartos.splice(
        cartos.findIndex((c) => c.id === id),
        1,
      );
    },
    async insererTravail(ligne) {
      if (options.echecTravail) return "erreur";
      const id = travaux.length + 100;
      travaux.push({ id, ...ligne });
      return id;
    },
    async lierTravail(cartoId, travailId) {
      const c = cartos.find((x) => x.id === cartoId);
      if (c) c.travailId = travailId;
      return Boolean(c);
    },
  };
  return { depot, cartos, travaux };
}

describe("lancerCartoAvec", () => {
  it("lance sur la dernière version validée, dans l'organisation du groupe", async () => {
    const { depot, cartos, travaux } = base(ORG_A);
    const r = await lancerCartoAvec(depot, "g-a");
    expect(r).toEqual({ statut: "ok", cartoId: "c-1", message: MESSAGES.lancee });
    expect(cartos).toEqual([
      {
        id: "c-1",
        organisationId: ORG_A,
        groupeId: "g-a",
        reglagesId: "r-a-2", // la v3 n'est pas validée
        statut: "en_attente",
        travailId: 100,
      },
    ]);
    expect(travaux).toEqual([{ id: 100, organisationId: ORG_A, cartoId: "c-1" }]);
  });

  it("refuse un groupe d'une autre organisation, sans rien écrire", async () => {
    const { depot, cartos, travaux } = base(ORG_A);
    expect(await lancerCartoAvec(depot, "g-b")).toEqual({ statut: "erreur", message: MESSAGES.groupeIntrouvable });
    expect(cartos).toEqual([]);
    expect(travaux).toEqual([]);
  });

  it("refuse sans version validée, en français", async () => {
    const { depot, cartos } = base(ORG_A);
    expect(await lancerCartoAvec(depot, "g-a-brouillon")).toEqual({
      statut: "erreur",
      message: MESSAGES.aucuneVersionValidee,
    });
    expect(cartos).toEqual([]);
  });

  it("refuse un second lancement tant qu'une carto est active", async () => {
    const { depot, cartos, travaux } = base(ORG_A);
    await lancerCartoAvec(depot, "g-a");
    expect(await lancerCartoAvec(depot, "g-a")).toEqual({ statut: "erreur", message: MESSAGES.dejaEnCours });
    expect(cartos).toHaveLength(1);
    expect(travaux).toHaveLength(1);
  });

  it("relance permise une fois la carto terminée", async () => {
    const { depot, cartos } = base(ORG_A);
    await lancerCartoAvec(depot, "g-a");
    cartos[0].statut = "terminee";
    expect((await lancerCartoAvec(depot, "g-a")).statut).toBe("ok");
  });

  it("lancement concurrent : la nôtre est retirée, aucun travail créé", async () => {
    const { depot, cartos, travaux } = base(ORG_A, { concurrent: true });
    expect(await lancerCartoAvec(depot, "g-a")).toEqual({ statut: "erreur", message: MESSAGES.dejaEnCours });
    expect(cartos.map((c) => c.id)).toEqual(["c-concurrent"]);
    expect(travaux).toEqual([]);
  });

  it("travail impossible à créer : la carto est retirée, aucune orpheline", async () => {
    const { depot, cartos } = base(ORG_A, { echecTravail: true });
    expect(await lancerCartoAvec(depot, "g-a")).toEqual({ statut: "erreur", message: MESSAGES.base });
    expect(cartos).toEqual([]);
  });
});
