// E-mails des auteurs de décisions (T028) : un dépôt en mémoire qui imite RLS
// sur `membres` (on ne voit que les membres de ses organisations) et compte les
// lectures d'e-mail en service_role.
import { describe, expect, it } from "vitest";

import { type DepotAuteurs, emailsDesAuteurs } from "./auteurs";

const MEMBRES: Record<string, string[]> = {
  "org-a": ["user-a1", "user-a2"],
  "org-b": ["user-b1"],
};
const EMAILS: Record<string, string> = {
  "user-a1": "a1@exemple.test",
  "user-a2": "a2@exemple.test",
  "user-b1": "b1@exemple.test",
};

function base(organisationsDuLecteur: string[]) {
  const lus: string[] = [];
  const depot: DepotAuteurs = {
    async membresDe(organisationId) {
      return organisationsDuLecteur.includes(organisationId) ? (MEMBRES[organisationId] ?? []) : [];
    },
    async emailDe(userId) {
      lus.push(userId);
      return EMAILS[userId] ?? null;
    },
  };
  return { depot, lus };
}

describe("emailsDesAuteurs", () => {
  it("rend l'e-mail des auteurs membres de l'organisation de la carto", async () => {
    const { depot } = base(["org-a"]);
    const emails = await emailsDesAuteurs(depot, "org-a", ["user-a1", "user-a2", null, "user-a1"]);
    expect(Object.fromEntries(emails)).toEqual({ "user-a1": "a1@exemple.test", "user-a2": "a2@exemple.test" });
  });

  it("un membre de B ne lit jamais l'e-mail d'un membre de A", async () => {
    const { depot, lus } = base(["org-b"]);
    // Même en demandant l'organisation A et ses auteurs : RLS ne lui montre aucun membre de A.
    expect((await emailsDesAuteurs(depot, "org-a", ["user-a1", "user-a2"])).size).toBe(0);
    // Et un auteur de A n'est jamais lu au titre de l'organisation B.
    expect((await emailsDesAuteurs(depot, "org-b", ["user-a1", "user-b1"])).get("user-a1")).toBeUndefined();
    expect(lus).toEqual(["user-b1"]);
  });

  it("un auteur qui n'est plus membre, ou sans adresse, n'a pas d'e-mail", async () => {
    const { depot, lus } = base(["org-a"]);
    const emails = await emailsDesAuteurs(depot, "org-a", ["user-parti", null]);
    expect(emails.size).toBe(0);
    expect(lus).toEqual([]);
  });
});
