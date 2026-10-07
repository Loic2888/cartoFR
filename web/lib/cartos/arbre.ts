// L'arbre d'une carto (T022, FR-007) : range les sociétés que le worker a
// écrites sous leur maison mère, pour l'affichage. Aucune règle du moteur ici
// (principe 7) : qui est filiale de qui est déjà décidé dans `carto_societes`.
//
// Sans dépendance serveur : importé par la page et par le composant client.

export type Confiance = "A" | "B" | "C";

/** Une ligne de `carto_societes`, telle que la page la lit. */
export type SocieteCarto = {
  siren: string;
  nom: string | null;
  niveau: number;
  maison_mere_siren: string | null;
  confiance: Confiance | null;
  preuve: string | null;
  ciblable: boolean;
  raison_ciblable: string | null;
  opposition_prospection: boolean;
  non_diffusible: boolean;
};

/** Un nœud de l'arbre : une société, ou le groupe « Rattachement inconnu ». */
export type Noeud = {
  /** Unique dans l'arbre : le SIREN, ou `INCONNU` pour le groupe des orphelines. */
  id: string;
  /** Null pour le groupe des orphelines. */
  societe: SocieteCarto | null;
  /** La maison mère directe, si elle est dans la carto. */
  maisonMere: { siren: string; nom: string | null } | null;
  enfants: Noeud[];
  /** Nombre de sociétés sous ce nœud, à tous les niveaux. */
  descendants: number;
};

export const INCONNU = "inconnu";

export const LIBELLE_INCONNU = "Rattachement inconnu";

/** La confiance en texte (le sens ne passe jamais par la seule couleur). Null : la tête. */
export function libelleConfiance(confiance: Confiance | null): string {
  switch (confiance) {
    case "A":
      return "A — lu au registre";
    case "B":
      return "B — au moins deux indices";
    case "C":
      return "C — à vérifier";
    default:
      return "Tête du groupe";
  }
}

/** « 552120222 » → « 552 120 222 ». Une valeur d'une autre forme est rendue telle quelle. */
export function sirenFr(siren: string): string {
  return /^\d{9}$/.test(siren) ? `${siren.slice(0, 3)} ${siren.slice(3, 6)} ${siren.slice(6)}` : siren;
}

const ordreNom = new Intl.Collator("fr", { sensitivity: "base", numeric: true });

/** Par nom (sans nom en dernier), puis par SIREN : un ordre stable d'un affichage à l'autre. */
function comparer(a: SocieteCarto, b: SocieteCarto): number {
  if (a.nom && !b.nom) return -1;
  if (!a.nom && b.nom) return 1;
  const parNom = a.nom && b.nom ? ordreNom.compare(a.nom, b.nom) : 0;
  return parNom !== 0 ? parNom : a.siren < b.siren ? -1 : a.siren > b.siren ? 1 : 0;
}

/**
 * Les racines de l'arbre : la tête (sans maison mère), puis, s'il y en a, le
 * groupe « Rattachement inconnu » avec les sociétés dont la maison mère n'est
 * pas dans la carto. Aucune société n'est perdue : une société que la descente
 * depuis la tête n'atteint pas (maison mère absente, ou boucle) va dans ce groupe.
 */
export function construireArbre(societes: readonly SocieteCarto[]): Noeud[] {
  const parSiren = new Map<string, SocieteCarto>();
  for (const s of societes) parSiren.set(s.siren, s);

  const enfantsDe = new Map<string, SocieteCarto[]>();
  for (const s of parSiren.values()) {
    if (s.maison_mere_siren === null || s.maison_mere_siren === s.siren) continue;
    const liste = enfantsDe.get(s.maison_mere_siren) ?? [];
    liste.push(s);
    enfantsDe.set(s.maison_mere_siren, liste);
  }
  for (const liste of enfantsDe.values()) liste.sort(comparer);

  const vus = new Set<string>();
  // Descente itérative : un arbre de 1 000 sociétés sur 10 niveaux ne fait pas
  // déborder la pile, et `vus` coupe une boucle éventuelle.
  function noeud(racine: SocieteCarto): Noeud {
    const creer = (s: SocieteCarto): Noeud => {
      vus.add(s.siren);
      const mere = s.maison_mere_siren ? parSiren.get(s.maison_mere_siren) : undefined;
      return {
        id: s.siren,
        societe: s,
        maisonMere: mere && mere.siren !== s.siren ? { siren: mere.siren, nom: mere.nom } : null,
        enfants: [],
        descendants: 0,
      };
    };
    const tete = creer(racine);
    const pile: Noeud[] = [tete];
    const ordre: Noeud[] = [];
    while (pile.length > 0) {
      const n = pile.pop()!;
      ordre.push(n);
      for (const e of enfantsDe.get(n.id) ?? []) {
        if (vus.has(e.siren)) continue;
        const enfant = creer(e);
        n.enfants.push(enfant);
        pile.push(enfant);
      }
    }
    // Les enfants sont déjà triés ; les descendants se comptent de bas en haut.
    for (let i = ordre.length - 1; i >= 0; i--) {
      const n = ordre[i];
      n.descendants = n.enfants.reduce((total, e) => total + 1 + e.descendants, 0);
    }
    return tete;
  }

  const triees = [...parSiren.values()].sort(comparer);
  const racines = triees
    .filter((s) => s.maison_mere_siren === null)
    .sort((a, b) => a.niveau - b.niveau || comparer(a, b))
    .map(noeud);

  const orphelines: Noeud[] = [];
  // D'abord celles dont la maison mère manque, puis ce qu'il reste (boucles).
  for (const s of triees) {
    if (!vus.has(s.siren) && s.maison_mere_siren !== null && !parSiren.has(s.maison_mere_siren)) {
      orphelines.push(noeud(s));
    }
  }
  for (const s of triees) if (!vus.has(s.siren)) orphelines.push(noeud(s));

  if (orphelines.length > 0) {
    racines.push({
      id: INCONNU,
      societe: null,
      maisonMere: null,
      enfants: orphelines,
      descendants: orphelines.reduce((total, e) => total + 1 + e.descendants, 0),
    });
  }
  return racines;
}

/** Les chiffres en tête de page. */
export function compter(societes: readonly SocieteCarto[]): {
  societes: number;
  ciblables: number;
  opposees: number;
  nonDiffusibles: number;
} {
  return {
    societes: societes.length,
    ciblables: societes.filter((s) => s.ciblable).length,
    opposees: societes.filter((s) => s.opposition_prospection).length,
    nonDiffusibles: societes.filter((s) => s.non_diffusible).length,
  };
}

/** Les nœuds visibles, dans l'ordre de lecture, avec leur parent : la base de la navigation au clavier. */
export function visibles(
  racines: readonly Noeud[],
  ouverts: ReadonlySet<string>,
): { noeud: Noeud; parent: string | null }[] {
  const sortie: { noeud: Noeud; parent: string | null }[] = [];
  const pile: { noeud: Noeud; parent: string | null }[] = [...racines]
    .reverse()
    .map((noeud) => ({ noeud, parent: null }));
  while (pile.length > 0) {
    const courant = pile.pop()!;
    sortie.push(courant);
    if (ouverts.has(courant.noeud.id)) {
      for (let i = courant.noeud.enfants.length - 1; i >= 0; i--) {
        pile.push({ noeud: courant.noeud.enfants[i], parent: courant.noeud.id });
      }
    }
  }
  return sortie;
}

/** Les identifiants de tous les nœuds qui ont des enfants (pour « Tout déplier »). */
export function parents(racines: readonly Noeud[]): string[] {
  const ids: string[] = [];
  const pile = [...racines];
  while (pile.length > 0) {
    const n = pile.pop()!;
    if (n.enfants.length > 0) {
      ids.push(n.id);
      pile.push(...n.enfants);
    }
  }
  return ids;
}
