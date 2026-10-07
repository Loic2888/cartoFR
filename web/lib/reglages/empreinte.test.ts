// L'empreinte web rend exactement celle du worker (cartofr.empreinte) : mêmes
// vecteurs que worker/tests/test_reglages.py, calculés par Python.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { empreinte, normaliser } from "./empreinte";

const FICHIER = fileURLToPath(
  new URL("../../../worker/tests/fixtures/reglages/empreintes.json", import.meta.url),
);
const { vecteurs } = JSON.parse(readFileSync(FICHIER, "utf8")) as {
  vecteurs: { nom: string; cle: string; empreinte: string }[];
};

describe("empreinte", () => {
  it("a des vecteurs", () => {
    expect(vecteurs.length).toBeGreaterThanOrEqual(10);
  });

  it.each(vecteurs.map((v) => [JSON.stringify(v.nom), v] as const))(
    "rend l'empreinte de Python pour %s",
    (_nom, v) => {
      expect(empreinte(v.nom, v.cle)).toBe(v.empreinte);
    },
  );

  it("normalise comme Python : bords, puis majuscules", () => {
    expect(normaliser("  lefèvre ")).toBe("LEFÈVRE");
    expect(normaliser("straße")).toBe("STRASSE");
    // Python garde ﻿ aux bords, et retire \x1c et \x85.
    expect(normaliser("\x1c\x85dupont﻿")).toBe("DUPONT﻿");
  });

  it("refuse une clé vide", () => {
    expect(() => empreinte("Dupont", "")).toThrow();
  });

  it("dépend de la clé", () => {
    expect(empreinte("Dupont", "a-FAKE")).not.toBe(empreinte("Dupont", "b-FAKE"));
    expect(empreinte("Dupont", "a-FAKE")).toMatch(/^[0-9a-f]{64}$/);
  });
});
