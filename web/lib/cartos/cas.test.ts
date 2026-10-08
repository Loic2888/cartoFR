// Cas douteux (T028) : libellés, dernière décision affichée, auteur sans nom,
// et l'enregistrement d'une décision avec un dépôt en mémoire qui imite RLS.
import { describe, expect, it } from "vitest";

import {
  type DecisionLue,
  type DepotCas,
  LIBELLE_TYPE,
  MESSAGES,
  TYPES_CAS,
  auteurFr,
  deciderAvec,
  decisionFr,
  dernieresDecisions,
  libelleType,
} from "./cas";

const MOI = "user-moi";

describe("libellés", () => {
  it("chaque type de cas écrit par le worker a un libellé français", () => {
    expect(TYPES_CAS.map((t) => LIBELLE_TYPE[t])).toEqual([
      "Confiance C",
      "Co-entreprise",
      "Participation sans contrôle",
      "Société étrangère",
      "Déjà tranché",
    ]);
  });

  it("un type inconnu n'affiche jamais la valeur brute", () => {
    expect(libelleType("joint_venture")).toBe("Autre cas");
  });

  it("l'auteur se dit « vous », par son e-mail, ancien membre ou compte supprimé", () => {
    const emails = new Map([["user-autre", "collegue@exemple.test"]]);
    expect(auteurFr(MOI, MOI, emails)).toBe("par vous");
    expect(auteurFr("user-autre", MOI, emails)).toBe("par collegue@exemple.test");
    expect(auteurFr("user-parti", MOI, emails)).toBe("par un ancien membre");
    expect(auteurFr(null, MOI, emails)).toBe("par un compte supprimé");
  });

  it("une décision se lit avec son état, sa date et son heure de Paris, et son auteur", () => {
    expect(
      decisionFr({ decision: "ecarter", decide_le: "2026-10-08T08:12:00+00:00", decide_par: MOI }, MOI, new Map()),
    ).toBe("Écartée le 08/10/2026 à 10:12, par vous");
    expect(
      decisionFr({ decision: "retenir", decide_le: "2026-12-31T23:30:00+00:00", decide_par: null }, MOI, new Map()),
    ).toBe("Retenue le 01/01/2027 à 00:30, par un compte supprimé");
  });
});

describe("dernière décision par société", () => {
  const d = (id: number, siren: string, decision: string, le: string): DecisionLue => ({
    id,
    siren,
    decision,
    decide_le: le,
    decide_par: MOI,
  });

  it("la plus récente l'emporte, même enregistrée avant", () => {
    const dernieres = dernieresDecisions([
      d(2, "900000001", "retenir", "2026-10-02T09:00:00+00:00"),
      d(1, "900000001", "ecarter", "2026-10-01T09:00:00+00:00"),
      d(4, "900000002", "ecarter", "2026-10-01T09:00:00+00:00"),
      d(3, "900000002", "retenir", "2026-10-03T09:00:00+00:00"),
    ]);
    expect(dernieres.get("900000001")?.decision).toBe("retenir");
    expect(dernieres.get("900000002")?.decision).toBe("retenir");
  });

  it("à date égale, la dernière enregistrée ; une valeur inconnue est ignorée", () => {
    const dernieres = dernieresDecisions([
      d(7, "900000001", "ecarter", "2026-10-01T09:00:00+00:00"),
      d(3, "900000001", "retenir", "2026-10-01T09:00:00+00:00"),
      d(9, "900000001", "peut-etre", "2026-10-05T09:00:00+00:00"),
    ]);
    expect(dernieres.get("900000001")?.id).toBe(7);
    expect(dernieresDecisions([]).size).toBe(0);
  });
});

describe("enregistrer une décision", () => {
  const CAS = [
    { groupeId: "g-a", cartoId: "c-a", siren: "900000050", organisationId: "org-a" },
    { groupeId: "g-b", cartoId: "c-b", siren: "900000050", organisationId: "org-b" },
  ];

  function base(organisationDuLecteur: string, echec = false) {
    const inserees: Parameters<DepotCas["insererDecision"]>[0][] = [];
    const depot: DepotCas = {
      async lireCas(groupeId, cartoId, siren) {
        const c = CAS.find(
          (x) =>
            x.groupeId === groupeId &&
            x.cartoId === cartoId &&
            x.siren === siren &&
            x.organisationId === organisationDuLecteur,
        );
        return c ? { organisationId: c.organisationId, groupeId: c.groupeId } : null;
      },
      async insererDecision(ligne) {
        if (echec) return "erreur";
        inserees.push(ligne);
        return { decideLe: "2026-10-08T08:12:00+00:00" };
      },
    };
    return { depot, inserees };
  }

  it("enregistre la décision avec son auteur, l'organisation et le groupe du cas lu", async () => {
    const { depot, inserees } = base("org-a");
    const r = await deciderAvec(depot, MOI, {
      groupeId: "g-a",
      cartoId: "c-a",
      siren: "900000050",
      decision: "ecarter",
    });
    expect(r).toEqual({
      statut: "ok",
      message: MESSAGES.ecarter,
      decision: "ecarter",
      decideLe: "2026-10-08T08:12:00+00:00",
    });
    expect(inserees).toEqual([
      {
        organisationId: "org-a",
        groupeId: "g-a",
        cartoId: "c-a",
        siren: "900000050",
        decision: "ecarter",
        auteur: MOI,
      },
    ]);
  });

  it("le cas d'une autre organisation est introuvable : rien n'est écrit", async () => {
    const { depot, inserees } = base("org-a");
    const r = await deciderAvec(depot, MOI, {
      groupeId: "g-b",
      cartoId: "c-b",
      siren: "900000050",
      decision: "retenir",
    });
    expect(r).toEqual({ statut: "erreur", message: MESSAGES.introuvable });
    expect(inserees).toEqual([]);
  });

  it("une carto d'un autre groupe que celui de l'adresse est introuvable", async () => {
    const { depot, inserees } = base("org-a");
    const r = await deciderAvec(depot, MOI, {
      groupeId: "g-autre",
      cartoId: "c-a",
      siren: "900000050",
      decision: "retenir",
    });
    expect(r.statut).toBe("erreur");
    expect(inserees).toEqual([]);
  });

  it("une écriture refusée par la base rend un message français sûr", async () => {
    const { depot } = base("org-a", true);
    const r = await deciderAvec(depot, MOI, {
      groupeId: "g-a",
      cartoId: "c-a",
      siren: "900000050",
      decision: "retenir",
    });
    expect(r).toEqual({ statut: "erreur", message: MESSAGES.base });
  });
});
