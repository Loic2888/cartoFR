import { afterEach, describe, expect, it, vi } from "vitest";

// `server-only` refuse d'être importé hors du serveur React : neutre en test.
vi.mock("server-only", () => ({}));

const { chercherSocietes, societeParSiren, MESSAGES_RECHERCHE } = await import("./recherche");

const URL_TEST = "http://recherche.test:8080";

function reponseJson(statut: number, corps: unknown): Response {
  return new Response(JSON.stringify(corps), {
    status: statut,
    headers: { "Content-Type": "application/json" },
  });
}

const FROMAGERIE = {
  siren: "100000001",
  nom: "FROMAGERIE ETHEREE",
  sigle: null,
  ville: "VILLEFICTIVE",
  statut: "active",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("chercherSocietes", () => {
  it("appelle /recherche sur l'hôte fixé, avec q encodé", async () => {
    const faux = vi.fn(async () => reponseJson(200, { resultats: [FROMAGERIE] }));
    const r = await chercherSocietes("Fromagerie & co/../x", { url: URL_TEST, fetch: faux });
    expect(r).toEqual({ ok: true, societes: [FROMAGERIE] });
    const appel = new URL(String((faux.mock.calls[0] as unknown[])[0]));
    expect(appel.origin).toBe(URL_TEST);
    expect(appel.pathname).toBe("/recherche");
    expect(appel.searchParams.get("q")).toBe("Fromagerie & co/../x");
  });

  it("ne garde que les champs de société, même si le service en rend d'autres", async () => {
    const faux = vi.fn(async () =>
      reponseJson(200, { resultats: [{ ...FROMAGERIE, dirigeant: "ZORGLUB Armandine" }] }),
    );
    const r = await chercherSocietes("fromagerie", { url: URL_TEST, fetch: faux });
    expect(r.ok).toBe(true);
    if (r.ok) expect(Object.keys(r.societes[0]).sort()).toEqual(["nom", "sigle", "siren", "statut", "ville"]);
  });

  it("traduit 503 registre_occupe en français", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const faux = vi.fn(async () => reponseJson(503, { erreur: "registre_occupe" }));
    expect(await chercherSocietes("lvmh", { url: URL_TEST, fetch: faux })).toEqual({
      ok: false,
      message: MESSAGES_RECHERCHE.occupe,
    });
  });

  it("traduit 503 registre_absent et 400", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const absent = vi.fn(async () => reponseJson(503, { erreur: "registre_absent" }));
    expect(await chercherSocietes("lvmh", { url: URL_TEST, fetch: absent })).toEqual({
      ok: false,
      message: MESSAGES_RECHERCHE.absent,
    });
    const court = vi.fn(async () => reponseJson(400, { erreur: "requete_trop_courte" }));
    expect(await chercherSocietes("l", { url: URL_TEST, fetch: court })).toEqual({
      ok: false,
      message: MESSAGES_RECHERCHE.tropCourte,
    });
  });

  it("traduit une panne réseau, sans journaliser le texte cherché", async () => {
    const journal = vi.spyOn(console, "error").mockImplementation(() => {});
    const faux = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    expect(await chercherSocietes("ZORGLUB", { url: URL_TEST, fetch: faux })).toEqual({
      ok: false,
      message: MESSAGES_RECHERCHE.injoignable,
    });
    expect(JSON.stringify(journal.mock.calls)).not.toContain("ZORGLUB");
  });

  it("refuse une réponse illisible", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const faux = vi.fn(async () => reponseJson(200, { resultats: [{ siren: "12" }] }));
    expect(await chercherSocietes("lvmh", { url: URL_TEST, fetch: faux })).toEqual({
      ok: false,
      message: MESSAGES_RECHERCHE.injoignable,
    });
  });

  it("sans RECHERCHE_URL, rend un message sans appeler le réseau", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.stubEnv("RECHERCHE_URL", "");
    const faux = vi.fn();
    expect(await chercherSocietes("lvmh", { fetch: faux })).toEqual({
      ok: false,
      message: MESSAGES_RECHERCHE.injoignable,
    });
    expect(faux).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
  });
});

describe("societeParSiren", () => {
  it("rend la société du SIREN demandé, ou null", async () => {
    const faux = vi.fn(async () => reponseJson(200, { resultats: [FROMAGERIE] }));
    expect(await societeParSiren("100000001", { url: URL_TEST, fetch: faux })).toEqual({
      ok: true,
      societe: FROMAGERIE,
    });
    expect(await societeParSiren("999999999", { url: URL_TEST, fetch: faux })).toEqual({
      ok: true,
      societe: null,
    });
  });
});
