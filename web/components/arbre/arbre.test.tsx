// @vitest-environment jsdom
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { type SocieteCarto, construireArbre } from "@/lib/cartos/arbre";

import { Arbre } from "./arbre";

afterEach(cleanup);

const societe = (siren: string, nom: string, champs: Partial<SocieteCarto> = {}): SocieteCarto => ({
  siren,
  nom,
  niveau: 1,
  maison_mere_siren: "100000000",
  confiance: "A",
  preuve: "président au registre",
  ciblable: true,
  raison_ciblable: "société active",
  opposition_prospection: false,
  non_diffusible: false,
  ...champs,
});

// Tête
// ├── Alpha            (confiance B, opposition, non diffusible)
// │   ├── Alpha A     (niveau 2)
// │   │   └── Alpha A1 (niveau 3)
// │   └── Alpha B   (niveau 2, ciblable Non)
// └── Bêta             (confiance C)
const SOCIETES: SocieteCarto[] = [
  societe("100000000", "Tête", { niveau: 0, maison_mere_siren: null, confiance: null, preuve: "tête choisie" }),
  societe("200000000", "Alpha", { confiance: "B", opposition_prospection: true, non_diffusible: true }),
  societe("210000000", "Alpha A", { niveau: 2, maison_mere_siren: "200000000" }),
  societe("211000000", "Alpha A1", { niveau: 3, maison_mere_siren: "210000000" }),
  societe("220000000", "Alpha B", {
    niveau: 2,
    maison_mere_siren: "200000000",
    ciblable: false,
    raison_ciblable: "société radiée",
  }),
  societe("300000000", "Bêta", { confiance: "C", preuve: "<script>alert(1)</script> marque au BODACC" }),
];

const rendre = (societes = SOCIETES) =>
  render(<Arbre racines={construireArbre(societes)} libelle="Arbre du groupe Tête" />);

const item = (nom: string) => screen.getByRole("treeitem", { name: nom });

describe("Arbre — rôles et attributs ARIA (C2)", () => {
  it("porte role=tree et un nom, chaque société role=treeitem avec aria-expanded si elle a des filiales", () => {
    rendre();
    const arbre = screen.getByRole("tree", { name: "Arbre du groupe Tête" });
    expect(arbre).toBeTruthy();

    const tete = item("Tête");
    expect(tete.getAttribute("aria-expanded")).toBe("true");
    expect(tete.getAttribute("aria-level")).toBe("1");
    expect(tete.getAttribute("aria-setsize")).toBe("1");
    expect(tete.getAttribute("aria-posinset")).toBe("1");

    // Seul le premier niveau est déplié au départ.
    const alpha = item("Alpha");
    expect(alpha.getAttribute("aria-expanded")).toBe("false");
    expect(alpha.getAttribute("aria-level")).toBe("2");
    expect(alpha.getAttribute("aria-posinset")).toBe("1");
    expect(alpha.getAttribute("aria-setsize")).toBe("2");
    expect(screen.queryByRole("treeitem", { name: "Alpha A" })).toBeNull();

    // Une feuille n'a pas d'aria-expanded.
    expect(item("Bêta").hasAttribute("aria-expanded")).toBe(false);
    // Le groupe des filiales (un <details> porte aussi le rôle group).
    expect(tete.querySelectorAll(':scope > ul[role="group"]')).toHaveLength(1);
  });

  it("un seul élément de l'arbre est dans l'ordre de tabulation", () => {
    rendre();
    const items = screen.getAllByRole("treeitem");
    expect(items.filter((i) => i.tabIndex === 0)).toHaveLength(1);
    expect(item("Tête").tabIndex).toBe(0);
  });
});

describe("Arbre — navigation au clavier (C1)", () => {
  it("Tab entre dans l'arbre, flèche bas et haut passent d'une société visible à l'autre", async () => {
    const u = userEvent.setup();
    rendre();
    await u.tab(); // Tout déplier
    await u.tab(); // Tout replier
    await u.tab();
    expect(document.activeElement).toBe(item("Tête"));

    await u.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(item("Alpha"));
    expect(item("Alpha").tabIndex).toBe(0);
    expect(item("Tête").tabIndex).toBe(-1);

    await u.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(item("Bêta"));
    await u.keyboard("{ArrowDown}"); // dernière : on reste
    expect(document.activeElement).toBe(item("Bêta"));

    await u.keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(item("Alpha"));
  });

  it("flèche droite déplie, puis va à la première filiale ; flèche gauche replie, puis remonte", async () => {
    const u = userEvent.setup();
    rendre();
    act(() => item("Tête").focus());
    await u.keyboard("{ArrowDown}");
    const alpha = item("Alpha");

    await u.keyboard("{ArrowRight}");
    expect(alpha.getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement).toBe(alpha);
    expect(item("Alpha A")).toBeTruthy();

    await u.keyboard("{ArrowRight}");
    expect(document.activeElement).toBe(item("Alpha A"));
    expect(item("Alpha A").getAttribute("aria-level")).toBe("3");

    // Trois niveaux : Alpha A se déplie, on descend à Alpha A1.
    await u.keyboard("{ArrowRight}{ArrowRight}");
    expect(document.activeElement).toBe(item("Alpha A1"));
    expect(item("Alpha A1").getAttribute("aria-level")).toBe("4");

    // Une feuille : flèche gauche remonte à la maison mère.
    await u.keyboard("{ArrowLeft}");
    expect(document.activeElement).toBe(item("Alpha A"));
    // Déplié : flèche gauche replie, le focus reste.
    await u.keyboard("{ArrowLeft}");
    expect(item("Alpha A").getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(item("Alpha A"));
    await u.keyboard("{ArrowLeft}");
    expect(document.activeElement).toBe(item("Alpha"));
  });

  it("Entrée et Espace déplient et replient", async () => {
    const u = userEvent.setup();
    rendre();
    act(() => item("Tête").focus());
    await u.keyboard("{ArrowDown}");
    await u.keyboard("{Enter}");
    expect(item("Alpha").getAttribute("aria-expanded")).toBe("true");
    await u.keyboard("{Enter}");
    expect(item("Alpha").getAttribute("aria-expanded")).toBe("false");
    await u.keyboard(" ");
    expect(item("Alpha").getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement).toBe(item("Alpha"));
  });

  it("Début et Fin vont à la première et à la dernière société visible", async () => {
    const u = userEvent.setup();
    rendre();
    act(() => item("Tête").focus());
    await u.keyboard("{End}");
    expect(document.activeElement).toBe(item("Bêta"));
    await u.keyboard("{Home}");
    expect(document.activeElement).toBe(item("Tête"));
  });

  it("Tout déplier et Tout replier ; l'élément actif replié passe à son ancêtre visible", async () => {
    const u = userEvent.setup();
    rendre();
    await u.click(screen.getByRole("button", { name: "Tout déplier" }));
    expect(screen.getAllByRole("treeitem")).toHaveLength(6);
    act(() => item("Alpha A1").focus());
    expect(item("Alpha A1").tabIndex).toBe(0);

    await u.click(screen.getByRole("button", { name: "Tout replier" }));
    expect(screen.getAllByRole("treeitem")).toHaveLength(1);
    expect(item("Tête").tabIndex).toBe(0);
  });

  it("Tab depuis une société mène à sa preuve ; Échap revient à la société ; les flèches n'y jouent pas", async () => {
    const u = userEvent.setup();
    rendre();
    act(() => item("Tête").focus());
    await u.keyboard("{ArrowDown}");
    await u.tab();
    const resume = document.activeElement as HTMLElement;
    expect(resume.tagName).toBe("SUMMARY");
    expect(item("Alpha").contains(resume)).toBe(true);

    await u.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(resume);

    await u.keyboard("{Escape}");
    expect(document.activeElement).toBe(item("Alpha"));
  });

  it("un clic sur le chevron déplie la société", async () => {
    const u = userEvent.setup();
    const { container } = rendre();
    await u.click(container.querySelector('[data-bascule="200000000"]')!);
    expect(item("Alpha").getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement).toBe(item("Alpha"));
  });
});

describe("Arbre — ce que chaque société affiche en texte (C3)", () => {
  it("confiance, ciblable avec sa raison, opposition à la prospection et non-diffusion", async () => {
    const u = userEvent.setup();
    rendre();
    await u.click(screen.getByRole("button", { name: "Tout déplier" }));

    const tete = within(item("Tête")).getAllByText(/Confiance :/)[0];
    expect(tete.textContent).toBe("Confiance : Tête du groupe");

    const alpha = item("Alpha");
    const ficheAlpha = document.getElementById(alpha.getAttribute("aria-describedby")!)!;
    expect(ficheAlpha.textContent).toContain("SIREN 200 000 000");
    expect(ficheAlpha.textContent).toContain("Niveau 1");
    expect(ficheAlpha.textContent).toContain("Maison mère : Tête (100 000 000)");
    expect(ficheAlpha.textContent).toContain("Confiance : B — au moins deux indices");
    expect(ficheAlpha.textContent).toContain("Ciblable : Oui — société active");
    expect(ficheAlpha.textContent).toContain("Opposition à la prospection");
    expect(ficheAlpha.textContent).toContain("Non diffusible (INSEE)");
    expect(ficheAlpha.textContent).toContain("3 sociétés en dessous");

    const ficheDeux = document.getElementById(item("Alpha B").getAttribute("aria-describedby")!)!;
    expect(ficheDeux.textContent).toContain("Ciblable : Non — société radiée");
    expect(ficheDeux.textContent).not.toContain("Opposition à la prospection");

    const ficheBeta = document.getElementById(item("Bêta").getAttribute("aria-describedby")!)!;
    expect(ficheBeta.textContent).toContain("Confiance : C — à vérifier");
  });

  it("la preuve est rendue comme du texte, jamais comme du HTML", () => {
    const { container } = rendre();
    expect(container.querySelector("script")).toBeNull();
    expect(within(item("Bêta")).getByText("<script>alert(1)</script> marque au BODACC")).toBeTruthy();
  });

  it("une carto réduite à la tête : un seul nœud, sans aria-expanded", () => {
    rendre([SOCIETES[0]]);
    const items = screen.getAllByRole("treeitem");
    expect(items).toHaveLength(1);
    expect(items[0].hasAttribute("aria-expanded")).toBe(false);
    expect(items[0].tabIndex).toBe(0);
  });

  it("une société dont la maison mère manque apparaît sous « Rattachement inconnu »", () => {
    rendre([SOCIETES[0], societe("400000000", "Orpheline", { maison_mere_siren: "999999999" })]);
    const inconnu = item("Rattachement inconnu");
    expect(inconnu.getAttribute("aria-expanded")).toBe("true");
    expect(within(inconnu).getByRole("treeitem", { name: "Orpheline" }).textContent).toContain(
      "Maison mère hors de la carto (999 999 999)",
    );
  });
});
