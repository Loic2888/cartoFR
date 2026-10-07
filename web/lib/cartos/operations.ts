// Lancer une carto (T021, FR-005) : la décision, séparée de la base pour être
// testée sans session (operations.test.ts). cartos/actions.ts branche un
// Depot sur Supabase.
//
// Règles :
// - le groupe est lu avec la session de l'utilisateur (RLS) : un groupe d'une
//   autre organisation est introuvable, rien n'est lancé. L'organisation de
//   la carto et du travail est celle du groupe ainsi lu, jamais une valeur
//   envoyée par le navigateur ;
// - la carto part sur la DERNIÈRE version validée des réglages (FR-005) ;
// - une seule carto active (en attente ou en cours) par groupe ;
// - aucune ligne orpheline : la carto est insérée d'abord, sans travail ; si
//   le travail ne s'insère pas, la carto est supprimée. Si seul le lien
//   carto → travail échoue, le worker le pose lui-même en prenant la carto.
//
// Double lancement : la base n'a pas d'index unique « une carto active par
// groupe » (supabase/ hors du périmètre de T021). On vérifie avant, puis de
// nouveau après l'insertion : si une autre carto active est apparue entre-
// temps, la nôtre est supprimée. Deux lancements simultanés peuvent alors
// être refusés tous les deux (sûr), jamais acceptés tous les deux.
import { MESSAGES, peutLancer } from "./affichage";

export interface Depot {
  /** Le groupe, lu sous RLS ; null s'il n'existe pas ou appartient à une autre organisation. */
  lireGroupe(groupeId: string): Promise<{ id: string; organisationId: string } | null>;
  /** La version validée de numéro le plus haut, ou null. */
  derniereVersionValidee(groupeId: string): Promise<{ id: string; version: number } | null>;
  /** Les ids des cartos actives (en attente ou en cours) du groupe. */
  cartosActives(groupeId: string): Promise<string[]>;
  insererCarto(ligne: {
    organisationId: string;
    groupeId: string;
    reglagesId: string;
  }): Promise<string | "erreur">;
  supprimerCarto(cartoId: string): Promise<void>;
  insererTravail(ligne: { organisationId: string; cartoId: string }): Promise<number | "erreur">;
  lierTravail(cartoId: string, travailId: number): Promise<boolean>;
}

export type Resultat =
  | { statut: "ok"; cartoId: string; message: string }
  | { statut: "erreur"; message: string };

export async function lancerCartoAvec(depot: Depot, groupeId: string): Promise<Resultat> {
  const groupe = await depot.lireGroupe(groupeId);
  if (!groupe) return { statut: "erreur", message: MESSAGES.groupeIntrouvable };

  const [version, actives] = await Promise.all([
    depot.derniereVersionValidee(groupe.id),
    depot.cartosActives(groupe.id),
  ]);
  const verdict = peutLancer({ versionValidee: version !== null, cartoActive: actives.length > 0 });
  if (!verdict.ok) return { statut: "erreur", message: verdict.message };
  if (!version) return { statut: "erreur", message: MESSAGES.aucuneVersionValidee };

  const cartoId = await depot.insererCarto({
    organisationId: groupe.organisationId,
    groupeId: groupe.id,
    reglagesId: version.id,
  });
  if (cartoId === "erreur") return { statut: "erreur", message: MESSAGES.base };

  // Deuxième vérification : un lancement concurrent a pu passer la première.
  const autres = (await depot.cartosActives(groupe.id)).filter((id) => id !== cartoId);
  if (autres.length > 0) {
    await depot.supprimerCarto(cartoId);
    return { statut: "erreur", message: MESSAGES.dejaEnCours };
  }

  const travailId = await depot.insererTravail({ organisationId: groupe.organisationId, cartoId });
  if (travailId === "erreur") {
    await depot.supprimerCarto(cartoId);
    return { statut: "erreur", message: MESSAGES.base };
  }
  // Sans ce lien, le worker le pose à la prise de la carto : pas un échec.
  await depot.lierTravail(cartoId, travailId);
  return { statut: "ok", cartoId, message: MESSAGES.lancee };
}
