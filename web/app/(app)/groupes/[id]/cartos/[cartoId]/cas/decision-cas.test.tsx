// @vitest-environment jsdom
// Boutons « Retenir » et « Écarter » d'un cas (T028, C3) : libellé explicite,
// utilisables au clavier, décision en vigueur annoncée, erreur lisible.
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MESSAGES } from "@/lib/cartos/cas";

const deciderCas = vi.fn();
const refresh = vi.fn();

vi.mock("./actions", () => ({ deciderCas: (...args: unknown[]) => deciderCas(...args) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const { DecisionCas } = await import("./decision-cas");

const PROPS = {
  groupeId: "11111111-1111-4111-8111-111111111111",
  cartoId: "22222222-2222-4222-8222-222222222222",
  siren: "900000050",
  designation: "SOCIETE INVENTEE (SIREN 900000050)",
};

beforeEach(() => {
  deciderCas.mockReset();
  refresh.mockReset();
});
afterEach(cleanup);

describe("DecisionCas", () => {
  it("chaque bouton a un libellé explicite qui commence par son texte visible", () => {
    render(<DecisionCas {...PROPS} enVigueur={null} />);
    const retenir = screen.getByRole("button", { name: "Retenir SOCIETE INVENTEE (SIREN 900000050) dans le groupe" });
    const ecarter = screen.getByRole("button", { name: "Écarter SOCIETE INVENTEE (SIREN 900000050) du groupe" });
    expect(retenir.textContent).toBe("Retenir");
    expect(ecarter.textContent).toBe("Écarter");
    expect(retenir.getAttribute("aria-pressed")).toBe("false");
    expect(ecarter.getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("group", { name: "Décision pour SOCIETE INVENTEE (SIREN 900000050)" })).toBeTruthy();
  });

  it("la décision en vigueur est le bouton enfoncé", () => {
    render(<DecisionCas {...PROPS} enVigueur="ecarter" />);
    expect(screen.getByRole("button", { name: /^Écarter/ }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: /^Retenir/ }).getAttribute("aria-pressed")).toBe("false");
  });

  it("au clavier : Tab puis Entrée envoie la décision, puis l'annonce", async () => {
    deciderCas.mockResolvedValue({
      statut: "ok",
      message: MESSAGES.ecarter,
      decision: "ecarter",
      decideLe: "2026-10-08T08:12:00+00:00",
    });
    const user = userEvent.setup();
    render(<DecisionCas {...PROPS} enVigueur={null} />);
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: /^Retenir/ }));
    await user.tab();
    await user.keyboard("{Enter}");
    expect(deciderCas).toHaveBeenCalledWith({
      groupeId: PROPS.groupeId,
      cartoId: PROPS.cartoId,
      siren: PROPS.siren,
      decision: "ecarter",
    });
    expect(await screen.findByText(MESSAGES.ecarter)).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Écarter/ }).getAttribute("aria-pressed")).toBe("true");
    expect(refresh).toHaveBeenCalled();
  });

  it("une erreur s'affiche en texte, sans rafraîchir", async () => {
    deciderCas.mockResolvedValue({ statut: "erreur", message: MESSAGES.introuvable });
    const user = userEvent.setup();
    render(<DecisionCas {...PROPS} enVigueur={null} />);
    await user.click(screen.getByRole("button", { name: /^Retenir/ }));
    expect((await screen.findByRole("alert")).textContent).toBe(`Erreur : ${MESSAGES.introuvable}`);
    expect(refresh).not.toHaveBeenCalled();
  });
});
