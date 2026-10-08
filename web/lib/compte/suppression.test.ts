// Suppression de son compte (T031) : la logique de compte/actions.ts, avec un
// dépôt en mémoire qui imite GoTrue. Adresses et identifiants inventés.
import { describe, expect, it } from "vitest";

import {
  type Appartenance,
  type Depot,
  MESSAGES,
  confirmationValide,
  consequences,
  supprimerCompteAvec,
} from "./suppression";

function gotrue(options: { session?: string | null; echec?: boolean } = {}) {
  const comptes = new Set(["u-1", "u-2"]);
  const journal: string[] = [];
  let session: string | null = options.session === undefined ? "u-1" : options.session;
  const depot: Depot = {
    async utilisateurCourant() {
      return session;
    },
    async supprimerUtilisateur(id) {
      journal.push(`supprimer ${id}`);
      if (options.echec) return "erreur";
      if (!comptes.has(id)) return "introuvable";
      comptes.delete(id);
      return "ok";
    },
    async fermerSession() {
      journal.push("fermer");
      session = null;
    },
  };
  return { depot, comptes, journal };
}

describe("confirmationValide", () => {
  it.each([
    ["SUPPRIMER", true],
    ["  SUPPRIMER ", true],
    ["supprimer", false],
    ["Supprimer", false],
    ["", false],
    ["SUPPRIMER MON COMPTE", false],
    [null, false],
    [undefined, false],
    [42, false],
  ])("%j → %s", (saisie, attendu) => {
    expect(confirmationValide(saisie)).toBe(attendu);
  });
});

describe("supprimerCompteAvec", () => {
  it("supprime le compte de la session, puis ferme la session", async () => {
    const { depot, comptes, journal } = gotrue();
    expect(await supprimerCompteAvec(depot, "SUPPRIMER")).toBeNull();
    expect(comptes.has("u-1")).toBe(false);
    expect(comptes.has("u-2")).toBe(true);
    expect(journal).toEqual(["supprimer u-1", "fermer"]);
  });

  it("refuse sans le mot de confirmation, sans rien toucher", async () => {
    const { depot, comptes, journal } = gotrue();
    expect(await supprimerCompteAvec(depot, "supprimer")).toEqual({
      statut: "erreur",
      message: MESSAGES.confirmation,
    });
    expect(comptes.size).toBe(2);
    expect(journal).toEqual([]);
  });

  it("session expirée : rien n'est supprimé, on demande de se reconnecter", async () => {
    const { depot, comptes, journal } = gotrue({ session: null });
    expect(await supprimerCompteAvec(depot, "SUPPRIMER")).toEqual({
      statut: "erreur",
      message: MESSAGES.sessionExpiree,
      session: true,
    });
    expect(comptes.size).toBe(2);
    expect(journal).toEqual([]);
  });

  it("échec de GoTrue : le compte reste et la session aussi", async () => {
    const { depot, journal } = gotrue({ echec: true });
    expect(await supprimerCompteAvec(depot, "SUPPRIMER")).toEqual({
      statut: "erreur",
      message: MESSAGES.echec,
    });
    expect(journal).toEqual(["supprimer u-1"]);
    expect(await depot.utilisateurCourant()).toBe("u-1");
  });

  it("double envoi : le second trouve un compte déjà supprimé, c'est un succès", async () => {
    const { depot, comptes, journal } = gotrue();
    // Les deux demandes partent avant que la session ne soit fermée.
    const deuxieme: Depot = { ...depot, utilisateurCourant: async () => "u-1" };
    const [a, b] = await Promise.all([
      supprimerCompteAvec(depot, "SUPPRIMER"),
      supprimerCompteAvec(deuxieme, "SUPPRIMER"),
    ]);
    expect(a).toBeNull();
    expect(b).toBeNull();
    expect(comptes.has("u-1")).toBe(false);
    expect(journal.filter((l) => l === "supprimer u-1")).toHaveLength(2);
  });

  it("après la suppression, une nouvelle demande voit une session fermée", async () => {
    const { depot } = gotrue();
    await supprimerCompteAvec(depot, "SUPPRIMER");
    expect(await supprimerCompteAvec(depot, "SUPPRIMER")).toMatchObject({ session: true });
  });
});

describe("consequences", () => {
  const m = (organisationId: string, userId: string, role: string, creeLe = "2026-01-01"): Appartenance => ({
    organisationId,
    userId,
    role,
    creeLe,
  });

  it("seul administrateur avec d'autres membres : un membre sera promu", () => {
    expect(consequences([m("o", "moi", "admin"), m("o", "b", "membre")], "moi")).toEqual([
      { organisationId: "o", cas: "promotion" },
    ]);
  });

  it("un autre administrateur reste : rien ne change", () => {
    expect(
      consequences([m("o", "moi", "admin"), m("o", "b", "admin"), m("o", "c", "membre")], "moi"),
    ).toEqual([{ organisationId: "o", cas: "rien" }]);
  });

  it("simple membre : rien ne change, même sans autre administrateur visible", () => {
    expect(consequences([m("o", "moi", "membre"), m("o", "b", "membre")], "moi")).toEqual([
      { organisationId: "o", cas: "rien" },
    ]);
  });

  it("dernier membre : l'organisation reste sans membre", () => {
    expect(consequences([m("o", "moi", "admin")], "moi")).toEqual([
      { organisationId: "o", cas: "sans_membre" },
    ]);
  });

  it("une conséquence par organisation du compte, aucune pour les autres", () => {
    const membres = [
      m("a", "moi", "admin"),
      m("a", "x", "membre"),
      m("b", "moi", "membre"),
      m("b", "y", "admin"),
      m("c", "z", "admin"),
    ];
    expect(consequences(membres, "moi")).toEqual([
      { organisationId: "a", cas: "promotion" },
      { organisationId: "b", cas: "rien" },
    ]);
  });

  it("aucune organisation : aucune conséquence", () => {
    expect(consequences([], "moi")).toEqual([]);
  });
});
