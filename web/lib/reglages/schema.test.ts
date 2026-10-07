// C1 : le schéma Zod rend le même verdict que pydantic (worker/tests/
// test_reglages.py) sur chaque fixture partagée. Le nom du fichier porte le
// verdict attendu : valide_*.json passe, invalide_*.json est refusé.
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { LISTES, longueur, schemaReglages, validerReglages } from "./schema";

const DOSSIER = fileURLToPath(new URL("../../../worker/tests/fixtures/reglages/", import.meta.url));
const fichiers = readdirSync(DOSSIER).filter((f) => f.endsWith(".json"));
const valides = fichiers.filter((f) => f.startsWith("valide_")).sort();
const invalides = fichiers.filter((f) => f.startsWith("invalide_")).sort();
const lire = (f: string): unknown => JSON.parse(readFileSync(DOSSIER + f, "utf8"));

describe("fixtures partagées avec pydantic (C1)", () => {
  it("existent", () => {
    expect(valides.length).toBeGreaterThanOrEqual(3);
    expect(invalides.length).toBeGreaterThanOrEqual(10);
  });

  it.each(valides)("accepte %s", (f) => {
    const verdict = validerReglages(lire(f));
    expect(verdict.ok ? [] : verdict.erreurs).toEqual([]);
  });

  it.each(invalides)("refuse %s", (f) => {
    expect(validerReglages(lire(f)).ok).toBe(false);
  });

  it.each(invalides)("le schéma seul refuse aussi %s", (f) => {
    expect(schemaReglages.safeParse(lire(f)).success).toBe(false);
  });
});

describe("validerReglages", () => {
  const base = { groupe: "Groupe Fictif", tete: "123456789" };

  it("refuse les familles en clair, sans recopier le nom", () => {
    const verdict = validerReglages({ ...base, familles_exclues: ["NOM FICTIF"] });
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) {
      expect(verdict.erreurs.join(" ")).toMatch(/jamais en clair/);
      expect(verdict.erreurs.join(" ")).not.toContain("NOM FICTIF");
    }
  });

  it("nomme le champ et la valeur fautive en français, sans la recopier", () => {
    const verdict = validerReglages({ ...base, exclus: ["775670417", "12345"], marques_sures: ["A\tB"] });
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) {
      expect(verdict.erreurs).toContain("SIREN exclus, valeur n° 2 : un SIREN fait 9 chiffres.");
      expect(verdict.erreurs.join(" ")).toMatch(/Marques sûres, valeur n° 1 : vide, ou contient/);
      expect(verdict.erreurs.join(" ")).not.toContain("12345.");
    }
  });

  it("dit qu'un champ obligatoire manque", () => {
    const verdict = validerReglages({ groupe: "Groupe Fictif" });
    expect(verdict.ok ? [] : verdict.erreurs).toEqual(["Tête du groupe : obligatoire."]);
  });

  it("compte les caractères comme Python (points de code)", () => {
    expect(longueur("😀".repeat(200))).toBe(200);
  });

  it("couvre toutes les listes du schéma dans l'écran", () => {
    const cles = Object.keys(schemaReglages.shape).filter(
      (c) => !["groupe", "tete", "familles_exclues_empreintes"].includes(c),
    );
    expect(LISTES.map((l) => l.cle).sort()).toEqual(cles.sort());
  });
});
