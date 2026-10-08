// L'identité (e-mail) des auteurs de décisions sur les cas douteux (T028,
// PRD US4 : « avec son nom »). Même chemin que l'écran des membres (T009) :
// les membres de l'organisation sont lus avec la session de l'utilisateur
// (RLS : seulement s'il en est membre), puis l'e-mail de ces seuls membres est
// lu dans auth.users avec la clé service_role, côté serveur.
//
// Règles :
// - un e-mail n'est lu que pour un auteur membre de l'organisation de la
//   carto, et seulement si l'utilisateur voit cette organisation (RLS). Un
//   membre de B ne lit donc jamais l'e-mail d'un membre de A ;
// - un auteur qui n'est plus membre (ou dont l'adresse est introuvable) n'a
//   pas d'e-mail : l'écran dit « un ancien membre » ;
// - aucun e-mail dans les journaux : seulement le code d'erreur.
//
// Sans dépendance serveur : la page branche le dépôt sur Supabase.

export interface DepotAuteurs {
  /** Les user_id des membres de l'organisation, lus sous RLS ; vide si l'utilisateur n'en est pas membre. */
  membresDe(organisationId: string): Promise<string[]>;
  /** L'e-mail d'un compte (service_role), ou null s'il est introuvable. */
  emailDe(userId: string): Promise<string | null>;
}

/** Les e-mails des auteurs donnés, pour les seuls membres de l'organisation que l'utilisateur voit. */
export async function emailsDesAuteurs(
  depot: DepotAuteurs,
  organisationId: string,
  auteurs: Iterable<string | null>,
): Promise<Map<string, string>> {
  const voulus = new Set([...auteurs].filter((a): a is string => a !== null));
  if (voulus.size === 0) return new Map();
  const membres = new Set(await depot.membresDe(organisationId));
  const lus = await Promise.all(
    [...voulus].filter((a) => membres.has(a)).map(async (a) => [a, await depot.emailDe(a)] as const),
  );
  return new Map(lus.filter((l): l is readonly [string, string] => l[1] !== null));
}
