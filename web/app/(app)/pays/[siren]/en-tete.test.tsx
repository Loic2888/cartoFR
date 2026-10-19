// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CartoPays } from "@/lib/pays";

import { EnTete } from "./en-tete";

afterEach(cleanup);

// Sociétés inventées (règle produit 6).
const societe = (siren: string, niveau: number, mere: string | null) => ({
  siren,
  nom: `SOCIETE ${siren}`,
  niveau,
  maison_mere_siren: mere,
  confiance: "A" as const,
  preuve: "Mandat au registre : Président",
  ciblable: true,
  raison_ciblable: "Société opérationnelle",
  opposition_prospection: niveau === 1,
  non_diffusible: false,
});

const SOUS_GROUPE: CartoPays = {
  siren: "100000061",
  nom: "TETE B INVENTEE",
  date_donnees: "2026-10-11",
  groupe: { tete: "100000061", nom: "TETE B INVENTEE", taille: 2 },
  groupe_entier: { tete: "100000060", nom: "TETE D INVENTEE", taille: 5 },
  mere: { siren: "100000060", nom: "TETE D INVENTEE" },
  mere_personne_physique: false,
  societes: [societe("100000061", 0, null), societe("100000062", 1, "100000061")],
};

describe("EnTete", () => {
  it("nomme la mère avec un lien vers sa carto, et le groupe entier (C6)", () => {
    render(<EnTete carto={SOUS_GROUPE} correction={null} />);
    expect(screen.getByRole("heading", { level: 1, name: "Carto de TETE B INVENTEE" })).toBeTruthy();
    const mere = screen.getByRole("link", { name: "TETE D INVENTEE" });
    expect(mere.getAttribute("href")).toBe("/pays/100000060");
    const entier = screen.getByRole("link", { name: "Voir le groupe TETE D INVENTEE en entier" });
    expect(entier.getAttribute("href")).toBe("/pays/100000060");
    expect(screen.getByText(/5 sociétés/)).toBeTruthy();
  });

  it("affiche la date des données et « calculée sans correction » (C4)", () => {
    render(<EnTete carto={SOUS_GROUPE} correction={null} />);
    expect(screen.getByText("11/10/2026")).toBeTruthy();
    expect(screen.getByText(/Calculée sans correction/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Voir la carto corrigée" })).toBeNull();
  });

  it("dit « personne physique, non affichée », sans lien (C3)", () => {
    const carto: CartoPays = {
      ...SOUS_GROUPE,
      groupe_entier: null,
      mere: null,
      mere_personne_physique: true,
    };
    render(<EnTete carto={carto} correction={null} />);
    expect(screen.getByText("Maison mère : personne physique, non affichée.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /TETE D|en entier/ })).toBeNull();
  });

  it("une tête de groupe n'a ni mère ni lien vers un groupe plus grand", () => {
    const carto: CartoPays = { ...SOUS_GROUPE, groupe_entier: null, mere: null };
    render(<EnTete carto={carto} correction={null} />);
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.queryByText(/Filiale de|personne physique/)).toBeNull();
  });

  it("mène à la carto corrigée de l'organisation quand elle existe", () => {
    render(<EnTete carto={SOUS_GROUPE} correction={{ groupeId: "g-1", cartoId: "c-1" }} />);
    const lien = screen.getByRole("link", { name: "Voir la carto corrigée" });
    expect(lien.getAttribute("href")).toBe("/groupes/g-1/cartos/c-1");
  });
});
