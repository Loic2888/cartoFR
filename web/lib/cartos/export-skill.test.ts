import type { SupabaseClient } from "@supabase/supabase-js";
import { afterEach, describe, expect, it, vi } from "vitest";

// `server-only` refuse d'être importé hors du serveur React : neutre en test.
vi.mock("server-only", () => ({}));

const { exporterSkill, MESSAGES_EXPORT_SKILL, FIN_FICHIER } = await import("./export-skill");

const URL_TEST = "http://recherche.test:8080";
const ORG_A = "0b8c7f9e-1a2b-4c3d-8e4f-5a6b7c8d9e01";
const ORG_B = "0b8c7f9e-1a2b-4c3d-8e4f-5a6b7c8d9e02";
const GROUPE_A = "1c8c7f9e-1a2b-4c3d-8e4f-5a6b7c8d9e01";
const CARTO_A = "2d8c7f9e-1a2b-4c3d-8e4f-5a6b7c8d9e01";
const CARTO_A_EN_COURS = "2d8c7f9e-1a2b-4c3d-8e4f-5a6b7c8d9e02";
const MEMBRE_A = "3e8c7f9e-1a2b-4c3d-8e4f-5a6b7c8d9e01";
const MEMBRE_B = "3e8c7f9e-1a2b-4c3d-8e4f-5a6b7c8d9e02";

type Ligne = Record<string, unknown>;

const TABLES: Record<string, Ligne[]> = {
  groupes: [{ id: GROUPE_A, organisation_id: ORG_A, nom: "Groupe Éthéré, « test »" }],
  cartos: [
    { id: CARTO_A, groupe_id: GROUPE_A, organisation_id: ORG_A, statut: "terminee", date_donnees: "2026-10-01" },
    { id: CARTO_A_EN_COURS, groupe_id: GROUPE_A, organisation_id: ORG_A, statut: "en_cours", date_donnees: null },
  ],
};
const MEMBRES: Record<string, string[]> = { [MEMBRE_A]: [ORG_A], [MEMBRE_B]: [ORG_B] };

/** Un client Supabase factice qui applique la politique RLS des tables de 0002 :
 * un membre ne lit que les lignes de ses organisations. */
function clientDe(utilisateur: string | null): SupabaseClient {
  const organisations = utilisateur ? (MEMBRES[utilisateur] ?? []) : [];
  return {
    auth: { getUser: async () => ({ data: { user: utilisateur ? { id: utilisateur } : null } }) },
    from(table: string) {
      const filtres: [string, unknown][] = [];
      let colonnes: string[] = [];
      const requete = {
        select(liste: string) {
          colonnes = liste.split(",").map((c) => c.trim());
          return requete;
        },
        eq(colonne: string, valeur: unknown) {
          filtres.push([colonne, valeur]);
          return requete;
        },
        async maybeSingle() {
          const visibles = (TABLES[table] ?? []).filter(
            (l) => organisations.includes(l.organisation_id as string) && filtres.every(([c, v]) => l[c] === v),
          );
          const ligne = visibles[0];
          return { data: ligne ? Object.fromEntries(colonnes.map((c) => [c, ligne[c]])) : null, error: null };
        },
      };
      return requete;
    },
  } as unknown as SupabaseClient;
}

function zip(): Response {
  return new Response(new Uint8Array([0x50, 0x4b, 0x05, 0x06]), {
    status: 200,
    headers: { "Content-Type": "application/zip" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("exporterSkill", () => {
  it("relaie le zip du worker pour un membre de l'organisation de la carto", async () => {
    const faux = vi.fn(async () => zip());
    const r = await exporterSkill(clientDe(MEMBRE_A), GROUPE_A, CARTO_A, { url: URL_TEST, fetch: faux });
    expect(r.status).toBe(200);
    expect(r.headers.get("Content-Type")).toBe("application/zip");
    expect(r.headers.get("Cache-Control")).toBe("no-store");
    const disposition = r.headers.get("Content-Disposition") ?? "";
    expect(disposition).toContain(`filename="cartofr-groupe-ethere-test-2026-10-01${FIN_FICHIER}"`);
    expect(new Uint8Array(await r.arrayBuffer())).toEqual(new Uint8Array([0x50, 0x4b, 0x05, 0x06]));

    const appel = new URL(String((faux.mock.calls[0] as unknown[])[0]));
    expect(appel.origin).toBe(URL_TEST);
    expect(appel.pathname).toBe(`/export/skill/${CARTO_A}`);
    // L'organisation vient de la ligne lue sous RLS, pas de la requête.
    expect(appel.searchParams.get("organisation")).toBe(ORG_A);
  });

  it("cloisonne : un membre de B ne télécharge pas la carto de A, et le worker n'est pas appelé", async () => {
    const faux = vi.fn(async () => zip());
    const r = await exporterSkill(clientDe(MEMBRE_B), GROUPE_A, CARTO_A, { url: URL_TEST, fetch: faux });
    expect(r.status).toBe(404);
    expect(await r.text()).toBe(MESSAGES_EXPORT_SKILL.introuvable);
    expect(faux).not.toHaveBeenCalled();
  });

  it("refuse sans session", async () => {
    const faux = vi.fn(async () => zip());
    const r = await exporterSkill(clientDe(null), GROUPE_A, CARTO_A, { url: URL_TEST, fetch: faux });
    expect(r.status).toBe(401);
    expect(await r.text()).toBe(MESSAGES_EXPORT_SKILL.connexion);
    expect(faux).not.toHaveBeenCalled();
  });

  it("rend 404 pour des identifiants qui ne sont pas des UUID", async () => {
    const faux = vi.fn(async () => zip());
    const r = await exporterSkill(clientDe(MEMBRE_A), "../x", CARTO_A, { url: URL_TEST, fetch: faux });
    expect(r.status).toBe(404);
    expect(faux).not.toHaveBeenCalled();
  });

  it("rend 409 pour une carto pas terminée", async () => {
    const faux = vi.fn(async () => zip());
    const r = await exporterSkill(clientDe(MEMBRE_A), GROUPE_A, CARTO_A_EN_COURS, { url: URL_TEST, fetch: faux });
    expect(r.status).toBe(409);
    expect(await r.text()).toBe(MESSAGES_EXPORT_SKILL.pasTerminee);
    expect(faux).not.toHaveBeenCalled();
  });

  it("traduit les erreurs du worker en français", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const cas: [number, number, string][] = [
      [404, 404, MESSAGES_EXPORT_SKILL.introuvable],
      [409, 409, MESSAGES_EXPORT_SKILL.pasTerminee],
      [503, 503, MESSAGES_EXPORT_SKILL.indisponible],
      [500, 502, MESSAGES_EXPORT_SKILL.base],
    ];
    for (const [statutWorker, attendu, message] of cas) {
      const faux = vi.fn(async () => new Response(JSON.stringify({ erreur: "x" }), { status: statutWorker }));
      const r = await exporterSkill(clientDe(MEMBRE_A), GROUPE_A, CARTO_A, { url: URL_TEST, fetch: faux });
      expect(r.status).toBe(attendu);
      expect(await r.text()).toBe(message);
    }
  });

  it("rend 503 si le worker est injoignable", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const faux = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    const r = await exporterSkill(clientDe(MEMBRE_A), GROUPE_A, CARTO_A, { url: URL_TEST, fetch: faux });
    expect(r.status).toBe(503);
    expect(await r.text()).toBe(MESSAGES_EXPORT_SKILL.indisponible);
  });
});
