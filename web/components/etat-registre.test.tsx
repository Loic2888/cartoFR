import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { LigneEtatRegistre } from "@/lib/etat-registre";

import { EtatRegistre } from "./etat-registre";

const MAINTENANT = new Date("2026-10-07T10:00:00Z");

const ligne = (source: string, champs: Partial<LigneEtatRegistre> = {}): LigneEtatRegistre => ({
  source,
  date_donnees: "2026-10-06",
  dernier_passage: "2026-10-07T00:00:00Z",
  statut: "succes",
  volumes: { jours: 1, fiches: 2500 },
  erreur: null,
  ...champs,
});

const rendu = (lignes: LigneEtatRegistre[]) =>
  renderToStaticMarkup(<EtatRegistre lignes={lignes} maintenant={MAINTENANT} />);

/** Le texte visible, sans balises. */
const texte = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/[ \t\n]+/g, " ");

describe("EtatRegistre", () => {
  it("C2 : un échec affiche sa date et sa cause", () => {
    const html = rendu([
      ligne("rne", {
        statut: "echec",
        dernier_passage: "2026-10-06T00:00:00Z",
        erreur: "registre inaccessible en écriture",
      }),
      ligne("sirene"),
    ]);
    const t = texte(html);
    expect(t).toContain("Échec du passage du 06/10/2026 à 02:00");
    expect(t).toContain("Cause : registre inaccessible en écriture");
  });

  it("C3 : le statut est écrit en texte, avec une icône décorative", () => {
    const html = rendu([ligne("rne", { statut: "quota" }), ligne("sirene", { statut: "en_cours" })]);
    const t = texte(html);
    expect(t).toContain("Statut : Quota INPI atteint, reprise la nuit prochaine");
    expect(t).toContain("Statut : En cours");
    expect(html).toMatch(/<svg[^>]*aria-hidden="true"/);
  });

  it("affiche les dates en jj/mm/aaaa et les volumes au format français", () => {
    const t = texte(rendu([ligne("rne"), ligne("sirene")]));
    expect(t).toContain("Date des données 06/10/2026");
    expect(t).toContain("Fiches appliquées 2 500");
    expect(t).toContain("Registre national des entreprises (INPI)");
    expect(t).toContain("SIRENE (INSEE)");
  });

  it("sans retard, pas de bandeau", () => {
    expect(rendu([ligne("rne"), ligne("sirene")])).not.toContain('role="alert"');
  });

  it("au-delà de 7 jours, un bandeau d'alerte dit l'âge des données", () => {
    const html = rendu([ligne("rne", { date_donnees: "2026-09-27" }), ligne("sirene")]);
    expect(html).toContain('role="alert"');
    expect(texte(html)).toContain("Données du registre vieilles de 10 jours : la cible est 7 jours au plus.");
  });

  it("une source jamais synchronisée est montrée et déclenche le bandeau", () => {
    const html = rendu([ligne("sirene")]);
    const t = texte(html);
    expect(t).toContain("Statut : Jamais synchronisé");
    expect(t).toContain("Dernier passage Jamais");
    expect(html).toContain('role="alert"');
  });
});
