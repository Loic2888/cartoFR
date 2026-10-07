// Page d'une carto (T022, FR-007) : la date de ses données, ses chiffres, et
// l'arbre du groupe avec la preuve, la confiance, l'indication ciblable,
// l'opposition à la prospection et la non-diffusion de chaque société.
//
// Lu avec la session (RLS) : une carto d'une autre organisation, ou d'un autre
// groupe que celui de l'adresse, n'existe pas pour l'utilisateur, d'où un 404.
// Les sociétés viennent de `carto_societes`, sans nom de personne
// (garde-fou 6, principe 6). Tant que la carto tourne, la page se relit
// toutes les 3 s.
import { CircleCheck, CircleX, Clock, LoaderCircle, TriangleAlert } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";

import { Arbre } from "@/components/arbre/arbre";
import { buttonVariants } from "@/components/ui/button";
import { type SocieteCarto, compter, construireArbre } from "@/lib/cartos/arbre";
import { type StatutCarto, dateDonneesFr, dureeFr, libelleStatut, uneBloquante } from "@/lib/cartos/affichage";
import { utilisateurCourant } from "@/lib/session";

import { dateFr } from "../../../organisation";
import { Rafraichir } from "./rafraichir";

export const metadata: Metadata = { title: "Carto · cartoFR" };

const heureFr = new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Paris",
});

const ICONES: Record<StatutCarto, React.ReactNode> = {
  en_attente: <Clock aria-hidden="true" className="size-4" />,
  en_cours: <LoaderCircle aria-hidden="true" className="size-4 motion-safe:animate-spin" />,
  terminee: <CircleCheck aria-hidden="true" className="size-4" />,
  echec: <CircleX aria-hidden="true" className="size-4 text-destructive" />,
};

const LIEN =
  "inline-flex min-h-11 items-center rounded-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring";

const COLONNES =
  "siren, nom, niveau, maison_mere_siren, confiance, preuve, ciblable, raison_ciblable, opposition_prospection, non_diffusible";

/** Taille d'une page de lecture : sous la limite de lignes que PostgREST peut imposer. */
const PAGE = 1000;

type Supabase = Awaited<ReturnType<typeof utilisateurCourant>>["supabase"];

/** Toutes les sociétés de la carto, page par page (VINCI en compte environ 1 000). */
async function lireSocietes(supabase: Supabase, cartoId: string): Promise<SocieteCarto[] | null> {
  const toutes: SocieteCarto[] = [];
  for (let debut = 0; ; debut += PAGE) {
    const { data, error } = await supabase
      .from("carto_societes")
      .select(COLONNES)
      .eq("carto_id", cartoId)
      .order("siren", { ascending: true })
      .range(debut, debut + PAGE - 1);
    if (error) {
      console.error("carto : lecture des sociétés impossible", { code: error.code });
      return null;
    }
    toutes.push(...((data ?? []) as SocieteCarto[]));
    if (!data || data.length < PAGE) return toutes;
  }
}

const nombre = (n: number) => n.toLocaleString("fr-FR");

export default async function Carto({ params }: PageProps<"/groupes/[id]/cartos/[cartoId]">) {
  const { id, cartoId } = await params;
  if (!z.uuid().safeParse(id).success || !z.uuid().safeParse(cartoId).success) notFound();

  const { supabase } = await utilisateurCourant();
  const [{ data: groupe }, { data: carto }] = await Promise.all([
    supabase.from("groupes").select("id, nom").eq("id", id).maybeSingle(),
    supabase
      .from("cartos")
      .select("id, statut, travail_id, cree_le, date_donnees, duree_ms, avertissement")
      .eq("id", cartoId)
      .eq("groupe_id", id)
      .maybeSingle(),
  ]);
  if (!groupe || !carto) notFound();

  const statut = carto.statut as string;
  const terminee = statut === "terminee";
  // Une carto orpheline (lancement interrompu) ne fait plus rafraîchir la page.
  const active = uneBloquante([
    { statut, travail_id: carto.travail_id as number | null, cree_le: carto.cree_le as string },
  ]);
  const orpheline = !terminee && statut !== "echec" && !active;

  const [societes, { count: nbLiens, error: erreurLiens }] = terminee
    ? await Promise.all([
        lireSocietes(supabase, cartoId),
        supabase.from("carto_liens").select("id", { count: "exact", head: true }).eq("carto_id", cartoId),
      ])
    : [[] as SocieteCarto[], { count: null, error: null }];
  if (erreurLiens) console.error("carto : comptage des liens impossible", { code: erreurLiens.code });

  const nomGroupe = groupe.nom as string;
  const lienGroupe = `/groupes/${id}`;
  const lancee = new Date(carto.cree_le as string);
  // Les chiffres n'ont de sens que sur une carto terminée : pas de « 0 » pendant le calcul.
  const chiffres = terminee && societes ? compter(societes) : null;
  const racines = societes ? construireArbre(societes) : [];

  return (
    <main className="flex flex-1 flex-col gap-6 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      {active ? <Rafraichir /> : null}

      <div className="flex flex-col gap-1">
        <Link href={lienGroupe} className={`${LIEN} self-start text-sm break-words`}>
          ← {nomGroupe}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight break-words">Carto de {nomGroupe}</h1>
      </div>

      <p className="flex items-center gap-2 font-medium" role="status">
        {ICONES[statut as StatutCarto] ?? null}
        <span>
          <span className="sr-only">Statut : </span>
          {libelleStatut(statut)}
        </span>
      </p>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="text-muted-foreground">Données du registre au</dt>
        <dd className="mb-2 font-medium sm:mb-0">{dateDonneesFr(carto.date_donnees as string | null)}</dd>
        <dt className="text-muted-foreground">Lancée le</dt>
        <dd className="mb-2 sm:mb-0">
          {dateFr.format(lancee)} à {heureFr.format(lancee)}
        </dd>
        <dt className="text-muted-foreground">Durée du calcul</dt>
        <dd className="mb-2 sm:mb-0">{dureeFr(carto.duree_ms as number | null)}</dd>
        {chiffres ? (
          <>
            <dt className="text-muted-foreground">Sociétés</dt>
            <dd className="mb-2 tabular-nums sm:mb-0">{nombre(chiffres.societes)}</dd>
            <dt className="text-muted-foreground">Liens au registre</dt>
            <dd className="mb-2 tabular-nums sm:mb-0">{nbLiens === null ? "—" : nombre(nbLiens)}</dd>
            <dt className="text-muted-foreground">Ciblables</dt>
            <dd className="mb-2 tabular-nums sm:mb-0">{nombre(chiffres.ciblables)}</dd>
            <dt className="text-muted-foreground">Opposées à la prospection</dt>
            <dd className="mb-2 tabular-nums sm:mb-0">{nombre(chiffres.opposees)}</dd>
            <dt className="text-muted-foreground">Non diffusibles (INSEE)</dt>
            <dd className="tabular-nums">{nombre(chiffres.nonDiffusibles)}</dd>
          </>
        ) : null}
      </dl>

      {carto.avertissement ? (
        <div
          role={statut === "echec" ? "alert" : "status"}
          className="flex gap-3 rounded-lg border border-amber-700/50 bg-amber-50 px-3 py-3 text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"
        >
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
          <p className="text-sm break-words">
            <strong className="font-semibold">Avertissement. </strong>
            {carto.avertissement as string}
          </p>
        </div>
      ) : null}

      {terminee ? (
        <div>
          {/* Fichier rendu par une route (T023) : un lien ordinaire, pas une navigation client. */}
          <a href={`/groupes/${id}/cartos/${cartoId}/export`} className={buttonVariants({ className: "w-full sm:w-auto" })}>
            Exporter (CSV)
          </a>
        </div>
      ) : null}

      <section aria-labelledby="titre-arbre" className="flex flex-col gap-4">
        <h2 id="titre-arbre" className="text-lg font-medium">
          Arbre du groupe
        </h2>
        {active ? (
          <p className="text-sm text-muted-foreground">
            Le calcul est {statut === "en_cours" ? "en cours" : "en attente"}. L&apos;arbre s&apos;affichera ici
            dès qu&apos;il sera terminé ; la page se met à jour toute seule.
          </p>
        ) : orpheline ? (
          <p className="text-sm">
            Cette carto n&apos;a jamais démarré. Relancez-la depuis la{" "}
            <Link href={lienGroupe} className={LIEN}>
              fiche du groupe
            </Link>
            .
          </p>
        ) : statut === "echec" ? (
          <p className="text-sm">
            Le calcul a échoué : il n&apos;y a pas d&apos;arbre. Vous pouvez relancer la carto depuis la{" "}
            <Link href={lienGroupe} className={LIEN}>
              fiche du groupe
            </Link>
            .
          </p>
        ) : societes === null ? (
          <p role="alert" className="text-sm text-destructive">
            Les sociétés de cette carto n&apos;ont pas pu être lues. Rechargez la page.
          </p>
        ) : (
          <Arbre racines={racines} libelle={`Arbre du groupe ${nomGroupe}`} />
        )}
      </section>
    </main>
  );
}
