// Fiche d'un groupe (T019) : sa tête, sa date de création, le lien vers ses
// réglages (T020), le lancement d'une carto et la liste de ses cartos (T021).
// Lu avec la session (RLS) : un groupe d'une autre organisation n'existe pas
// pour l'utilisateur, d'où un 404.
import { CircleCheck, CircleX, Clock, LoaderCircle } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";

import { buttonVariants } from "@/components/ui/button";
import {
  type StatutCarto,
  dateDonneesFr,
  dureeFr,
  libelleStatut,
  peutLancer,
  uneBloquante,
} from "@/lib/cartos/affichage";
import { utilisateurCourant } from "@/lib/session";

import { dateFr } from "../organisation";
import { LancerCarto } from "./cartos/lancer-carto";

export const metadata: Metadata = { title: "Groupe · cartoFR" };

const heureFr = new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Paris",
});

type LigneCarto = {
  id: string;
  statut: string;
  travail_id: number | null;
  cree_le: string;
  date_donnees: string | null;
  duree_ms: number | null;
  avertissement: string | null;
};

const ICONES: Record<StatutCarto, React.ReactNode> = {
  en_attente: <Clock aria-hidden="true" className="size-4" />,
  en_cours: <LoaderCircle aria-hidden="true" className="size-4 motion-safe:animate-spin" />,
  terminee: <CircleCheck aria-hidden="true" className="size-4" />,
  echec: <CircleX aria-hidden="true" className="size-4 text-destructive" />,
};

const LIEN =
  "inline-flex min-h-11 items-center rounded-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring";

export default async function Groupe({ params }: PageProps<"/groupes/[id]">) {
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) notFound();

  const { supabase } = await utilisateurCourant();
  const [{ data: groupe }, { data: validee }, { data: cartos, error: erreurCartos }] = await Promise.all([
    supabase.from("groupes").select("id, nom, tete_siren, cree_le").eq("id", id).maybeSingle(),
    supabase
      .from("reglages")
      .select("version")
      .eq("groupe_id", id)
      .not("valide_le", "is", null)
      .order("version", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("cartos")
      .select("id, statut, travail_id, cree_le, date_donnees, duree_ms, avertissement")
      .eq("groupe_id", id)
      .order("cree_le", { ascending: false })
      .limit(20),
  ]);
  if (!groupe) notFound();
  if (erreurCartos) console.error("groupe : lecture des cartos impossible", { code: erreurCartos.code });

  const lignes = (cartos ?? []) as LigneCarto[];
  const actif = uneBloquante(lignes);
  const verdict = peutLancer({ versionValidee: Boolean(validee), cartoActive: actif });
  const reglages = `/groupes/${groupe.id as string}/reglages`;

  return (
    <main className="flex flex-1 flex-col gap-6 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <div className="flex flex-col gap-1">
        <Link href="/groupes" className={`${LIEN} self-start text-sm`}>
          ← Groupes
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight break-words">{groupe.nom as string}</h1>
      </div>

      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="text-muted-foreground">SIREN de la tête</dt>
        <dd className="font-mono tabular-nums">{groupe.tete_siren as string}</dd>
        <dt className="text-muted-foreground">Créé le</dt>
        <dd>{dateFr.format(new Date(groupe.cree_le as string))}</dd>
        <dt className="text-muted-foreground">Réglages validés</dt>
        <dd>{validee ? `version ${validee.version as number}` : "aucune version validée"}</dd>
      </dl>

      <div>
        <Link href={reglages} className={buttonVariants({ className: "w-full sm:w-auto" })}>
          Réglages
        </Link>
      </div>

      <section aria-labelledby="titre-cartos" className="flex flex-col gap-4">
        <h2 id="titre-cartos" className="text-lg font-medium">
          Cartos
        </h2>
        <LancerCarto
          groupeId={groupe.id as string}
          empechement={verdict.ok ? null : verdict.message}
          lienReglages={
            validee ? null : (
              <Link href={reglages} className={LIEN}>
                Ouvrir les réglages
              </Link>
            )
          }
          actif={actif}
        />

        {erreurCartos ? (
          <p role="alert" className="text-sm text-destructive">
            Les cartos de ce groupe n&apos;ont pas pu être lues. Rechargez la page.
          </p>
        ) : lignes.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune carto lancée pour ce groupe.</p>
        ) : (
          <ul className="flex flex-col gap-3" aria-label="Cartos du groupe, la plus récente d'abord">
            {lignes.map((c) => {
              const lancee = new Date(c.cree_le);
              return (
                <li key={c.id} className="rounded-lg border px-4 py-3 text-sm">
                  <p className="flex items-center gap-2 font-medium">
                    {ICONES[c.statut as StatutCarto] ?? null}
                    <span>{libelleStatut(c.statut)}</span>
                  </p>
                  <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
                    <dt className="text-muted-foreground">Lancée le</dt>
                    <dd>
                      {dateFr.format(lancee)} à {heureFr.format(lancee)}
                    </dd>
                    <dt className="text-muted-foreground">Durée</dt>
                    <dd>{dureeFr(c.duree_ms)}</dd>
                    <dt className="text-muted-foreground">Données au</dt>
                    <dd>{dateDonneesFr(c.date_donnees)}</dd>
                  </dl>
                  {c.avertissement ? (
                    <p className="mt-2 rounded-md border px-3 py-2 break-words">
                      <span className="font-medium">Avertissement : </span>
                      {c.avertissement}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
