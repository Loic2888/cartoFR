// En-tête de la carto d'une société (T050) : sa mère au-dessus d'elle, le
// groupe plus grand dont elle fait partie, la date des données et la mention
// « calculée sans correction ». Pur affichage de la réponse du worker
// (principe 7) : rien n'est décidé ici.
import Link from "next/link";

import { compter, sirenFr } from "@/lib/cartos/arbre";
import { dateDonneesFr } from "@/lib/cartos/affichage";
import type { CartoPays } from "@/lib/pays";

const LIEN =
  "inline-flex min-h-11 items-center rounded-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring";

const nombre = (n: number) => n.toLocaleString("fr-FR");

/** Une carto du groupe faite par l'organisation, avec ses propres réglages. */
export type Correction = { groupeId: string; cartoId: string } | null;

export function nomAffiche(c: { siren: string; nom: string | null }): string {
  return c.nom ?? `SIREN ${sirenFr(c.siren)}`;
}

export function EnTete({ carto, correction }: { carto: CartoPays; correction: Correction }) {
  const nom = nomAffiche(carto);
  const chiffres = compter(carto.societes);
  const entier = carto.groupe_entier;
  return (
    <>
      <div className="flex flex-col gap-1">
        {carto.mere ? (
          <p className="text-sm">
            <span className="text-muted-foreground">Filiale de </span>
            <Link href={`/pays/${carto.mere.siren}`} className={`${LIEN} break-words`}>
              {nomAffiche(carto.mere)}
            </Link>
          </p>
        ) : carto.mere_personne_physique ? (
          <p className="text-sm text-muted-foreground">Maison mère : personne physique, non affichée.</p>
        ) : null}
        <h1 className="text-2xl font-semibold tracking-tight break-words">Carto de {nom}</h1>
        <p className="text-sm text-muted-foreground">
          SIREN <span className="font-mono tabular-nums">{sirenFr(carto.siren)}</span> : la société et
          tout ce qui descend d&apos;elle en France.
        </p>
      </div>

      {entier ? (
        <p className="text-sm">
          Elle fait partie du groupe {nomAffiche({ siren: entier.tete, nom: entier.nom })} ({nombre(entier.taille)}{" "}
          {entier.taille > 1 ? "sociétés" : "société"}).{" "}
          <Link href={`/pays/${entier.tete}`} className={LIEN}>
            Voir le groupe {nomAffiche({ siren: entier.tete, nom: entier.nom })} en entier
          </Link>
        </p>
      ) : null}

      <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="text-muted-foreground">Données du registre au</dt>
        <dd className="mb-2 font-medium sm:mb-0">{dateDonneesFr(carto.date_donnees)}</dd>
        <dt className="text-muted-foreground">Carto</dt>
        <dd className="mb-2 sm:mb-0">Calculée sans correction, à partir du registre et des documents publiés</dd>
        <dt className="text-muted-foreground">Sociétés</dt>
        <dd className="mb-2 tabular-nums sm:mb-0">{nombre(chiffres.societes)}</dd>
        <dt className="text-muted-foreground">Ciblables</dt>
        <dd className="mb-2 tabular-nums sm:mb-0">{nombre(chiffres.ciblables)}</dd>
        <dt className="text-muted-foreground">Opposées à la prospection</dt>
        <dd className="mb-2 tabular-nums sm:mb-0">{nombre(chiffres.opposees)}</dd>
        <dt className="text-muted-foreground">Non diffusibles (INSEE)</dt>
        <dd className="tabular-nums">{nombre(chiffres.nonDiffusibles)}</dd>
      </dl>

      {correction ? (
        <p className="text-sm">
          Votre organisation a aussi une carto corrigée de cette société, avec ses propres réglages.{" "}
          <Link href={`/groupes/${correction.groupeId}/cartos/${correction.cartoId}`} className={LIEN}>
            Voir la carto corrigée
          </Link>
        </p>
      ) : null}
    </>
  );
}
