import { afterEach, describe, expect, it, vi } from "vitest";

// `server-only` refuse d'être importé hors du serveur React : neutre en test.
vi.mock("server-only", () => ({}));

const { lireCartoPays, lignesExport, MESSAGES_PAYS } = await import("./pays");

const URL_TEST = "http://recherche.test:8080";

function reponseJson(statut: number, corps: unknown): Response {
  return new Response(JSON.stringify(corps), {
    status: statut,
    headers: { "Content-Type": "application/json" },
  });
}

// Sociétés inventées (règle produit 6).
const FILLE = "100000001";
const TETE = "100000006";
const PETITE_FILLE = "100000002";

const societe = (siren: string, niveau: number, mere: string | null) => ({
  siren,
  nom: `SOCIETE ${siren}`,
  niveau,
  maison_mere_siren: mere,
  confiance: "A",
  preuve: "Mandat au registre : Président",
  ciblable: true,
  raison_ciblable: "Société opérationnelle",
  opposition_prospection: false,
  non_diffusible: false,
});

const CARTO = {
  siren: FILLE,
  nom: `SOCIETE ${FILLE}`,
  date_donnees: "2026-10-11",
  groupe: { tete: TETE, nom: "BOULONNERIE QUANTIQUE", taille: 3 },
  groupe_entier: { tete: TETE, nom: "BOULONNERIE QUANTIQUE", taille: 3 },
  mere: { siren: TETE, nom: "BOULONNERIE QUANTIQUE" },
  mere_personne_physique: false,
  societes: [societe(FILLE, 0, null), societe(PETITE_FILLE, 1, FILLE)],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("lireCartoPays", () => {
  it("appelle /groupe sur l'hôte fixé avec le SIREN", async () => {
    const faux = vi.fn(async () => reponseJson(200, CARTO));
    const r = await lireCartoPays(FILLE, { url: URL_TEST, fetch: faux });
    expect(r).toEqual({ ok: true, carto: CARTO });
    const appel = new URL(String((faux.mock.calls[0] as unknown[])[0]));
    expect(appel.origin).toBe(URL_TEST);
    expect(appel.pathname).toBe("/groupe");
    expect(appel.searchParams.get("siren")).toBe(FILLE);
  });

  it("refuse un SIREN mal formé sans appeler le service", async () => {
    const faux = vi.fn();
    for (const valeur of ["", "12345678", "1234567890", "abc", "../sante"]) {
      const r = await lireCartoPays(valeur, { url: URL_TEST, fetch: faux });
      expect(r).toMatchObject({ ok: false, introuvable: true });
    }
    expect(faux).not.toHaveBeenCalled();
  });

  it("ne garde que les champs attendus : jamais un champ de personne", async () => {
    const faux = vi.fn(async () =>
      reponseJson(200, {
        ...CARTO,
        dirigeant: "ZORGLUB Armandine",
        societes: CARTO.societes.map((s) => ({ ...s, dirigeant: "ZORGLUB Armandine" })),
      }),
    );
    const r = await lireCartoPays(FILLE, { url: URL_TEST, fetch: faux });
    expect(r.ok).toBe(true);
    expect(JSON.stringify(r)).not.toContain("ZORGLUB");
  });

  it("traduit 404 et les 503 en français", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const cas: [number, unknown, string, boolean][] = [
      [404, { erreur: "societe_inconnue" }, MESSAGES_PAYS.introuvable, true],
      [503, { erreur: "pays_absent" }, MESSAGES_PAYS.pasCalculee, false],
      [503, { erreur: "registre_absent" }, MESSAGES_PAYS.absent, false],
      [503, { erreur: "registre_occupe" }, MESSAGES_PAYS.occupe, false],
      [500, { erreur: "erreur_interne" }, MESSAGES_PAYS.injoignable, false],
    ];
    for (const [statut, corps, message, introuvable] of cas) {
      const r = await lireCartoPays(FILLE, { url: URL_TEST, fetch: async () => reponseJson(statut, corps) });
      expect(r).toMatchObject({ ok: false, message, introuvable });
    }
  });

  it("rejette une réponse illisible ou pour un autre SIREN", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    for (const corps of [{ ...CARTO, societes: [] }, { ...CARTO, siren: TETE }, { resultats: [] }]) {
      const r = await lireCartoPays(FILLE, { url: URL_TEST, fetch: async () => reponseJson(200, corps) });
      expect(r).toMatchObject({ ok: false, message: MESSAGES_PAYS.injoignable });
    }
  });

  it("service injoignable ou adresse manquante", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const panne = async () => {
      throw new TypeError("fetch failed");
    };
    expect(await lireCartoPays(FILLE, { url: URL_TEST, fetch: panne })).toMatchObject({
      ok: false,
      message: MESSAGES_PAYS.injoignable,
    });
    vi.stubEnv("RECHERCHE_URL", "");
    expect(await lireCartoPays(FILLE)).toMatchObject({ ok: false, message: MESSAGES_PAYS.injoignable });
    vi.unstubAllEnvs();
  });
});

describe("lignesExport", () => {
  it("rend à la société demandée le SIREN de sa mère", () => {
    const lignes = lignesExport(CARTO as Parameters<typeof lignesExport>[0]);
    expect(lignes.map((l) => [l.siren, l.maison_mere_siren])).toEqual([
      [FILLE, TETE],
      [PETITE_FILLE, FILLE],
    ]);
  });

  it("laisse vide la mère d'une société dont la mère est une personne physique", () => {
    const c = { ...CARTO, mere: null, mere_personne_physique: true } as Parameters<typeof lignesExport>[0];
    expect(lignesExport(c)[0].maison_mere_siren).toBeNull();
  });

  it("écrit la tête sans confiance, comme l'export T023 (« Tête du groupe »)", () => {
    const tete = { ...CARTO, mere: null } as Parameters<typeof lignesExport>[0];
    const lignes = lignesExport(tete);
    expect(lignes[0].confiance).toBeNull();
    expect(lignes[1].confiance).toBe("A");
    expect(lignesExport(CARTO as Parameters<typeof lignesExport>[0])[0].confiance).toBe("A");
  });
});
