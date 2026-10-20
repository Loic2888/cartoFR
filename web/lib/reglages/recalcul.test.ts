// « Enregistrer et recalculer » (T051) : la version enregistrée relance la carto.
import { describe, expect, it, vi } from "vitest";

import { MESSAGES as MESSAGES_CARTOS } from "@/lib/cartos/affichage";

import { MESSAGES_RECALCUL, puisRecalculer } from "./recalcul";

const ENREGISTREE = { statut: "ok", version: 4, message: "Version 4 des corrections enregistrée." } as const;

describe("puisRecalculer", () => {
  it("relance la carto après un enregistrement réussi, et le dit", async () => {
    const lancer = vi.fn(async () => ({ statut: "ok" as const, cartoId: "c-1", message: MESSAGES_CARTOS.lancee }));
    const r = await puisRecalculer(ENREGISTREE, lancer);
    expect(lancer).toHaveBeenCalledOnce();
    expect(r).toEqual({ ...ENREGISTREE, message: `${ENREGISTREE.message} ${MESSAGES_RECALCUL.relancee}` });
  });

  it("ne lance rien si l'enregistrement a échoué", async () => {
    const lancer = vi.fn();
    const echec = { statut: "erreur", message: "Rien n'a changé." } as const;
    expect(await puisRecalculer(echec, lancer)).toBe(echec);
    expect(lancer).not.toHaveBeenCalled();
  });

  it("garde la version quand une carto est déjà en cours, et dit pourquoi rien n'est relancé", async () => {
    const r = await puisRecalculer(ENREGISTREE, async () => ({
      statut: "erreur",
      message: MESSAGES_CARTOS.dejaEnCours,
    }));
    expect(r.statut).toBe("ok");
    expect(r.message).toBe(
      `${ENREGISTREE.message} ${MESSAGES_RECALCUL.nonRelancee} une carto de ce groupe est déjà en attente ou en cours. Attendez qu'elle se termine avant d'en lancer une autre.`,
    );
  });

  it("une exception au lancement devient un message français, la version reste enregistrée", async () => {
    const r = await puisRecalculer(ENREGISTREE, async () => {
      throw new Error("connection refused");
    });
    expect(r.statut).toBe("ok");
    expect(r.message).toContain(MESSAGES_RECALCUL.echecLancement);
    expect(r.message).not.toContain("connection");
  });
});
