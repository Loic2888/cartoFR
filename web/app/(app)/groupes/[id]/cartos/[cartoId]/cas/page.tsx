// Cas douteux d'une carto (T028, FR-009) : chaque cas rangé par le moteur,
// avec la règle qui l'a placé là, ses indices pour et contre, et les boutons
// « Retenir » ou « Écarter ». La décision vaut pour le groupe : le worker la
// reprend à la carto suivante (T027). Cette carto-ci ne change pas.
//
// Lu avec la session (RLS) : une carto d'une autre organisation, ou d'un autre
// groupe que celui de l'adresse, n'existe pas pour l'utilisateur, d'où un 404.
// Les textes viennent de `carto_cas`, écrits par le worker sans nom de personne
// (garde-fou 6). L'auteur d'une décision se dit « vous », ou par son e-mail
// s'il est membre de l'organisation de la carto (lu côté serveur, comme
// l'écran des membres : lib/cartos/auteurs.ts), « un ancien membre » ou « un
// compte supprimé ». Aucun e-mail dans les journaux.
//
// Mobile d'abord : une liste de cartes, une colonne, boutons pleine largeur.
import { CircleCheck, CircleMinus, CirclePlus, CircleX } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";

import {
  type CasCarto,
  type DecisionLue,
  LIBELLE_DECISION,
  decisionFr,
  dernieresDecisions,
  estDecision,
  libelleType,
} from "@/lib/cartos/cas";
import { type DepotAuteurs, emailsDesAuteurs } from "@/lib/cartos/auteurs";
import { utilisateurCourant } from "@/lib/session";
import { creerClientAdmin } from "@/lib/supabase/admin";

import { DecisionCas } from "./decision-cas";

export const metadata: Metadata = { title: "Cas douteux · cartoFR" };

const LIEN =
  "inline-flex min-h-11 items-center rounded-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring";

const COLONNES = "siren, nom, types, regle, retenue, indices_pour, indices_contre, decision";

/** Taille d'une page de lecture : sous la limite de lignes que PostgREST peut imposer. */
const PAGE = 1000;

type Supabase = Awaited<ReturnType<typeof utilisateurCourant>>["supabase"];

async function lireTout<T>(
  lire: (debut: number, fin: number) => PromiseLike<{ data: unknown[] | null; error: { code: string } | null }>,
  quoi: string,
): Promise<T[] | null> {
  const tout: T[] = [];
  for (let debut = 0; ; debut += PAGE) {
    const { data, error } = await lire(debut, debut + PAGE - 1);
    if (error) {
      console.error(`cas : lecture ${quoi} impossible`, { code: error.code });
      return null;
    }
    tout.push(...((data ?? []) as T[]));
    if (!data || data.length < PAGE) return tout;
  }
}

function lireCas(supabase: Supabase, cartoId: string) {
  return lireTout<CasCarto>(
    (debut, fin) =>
      supabase
        .from("carto_cas")
        .select(COLONNES)
        .eq("carto_id", cartoId)
        .order("siren", { ascending: true })
        .range(debut, fin),
    "des cas",
  );
}

function lireDecisions(supabase: Supabase, groupeId: string) {
  return lireTout<DecisionLue>(
    (debut, fin) =>
      supabase
        .from("decisions")
        .select("id, siren, decision, decide_le, decide_par")
        .eq("groupe_id", groupeId)
        .order("id", { ascending: true })
        .range(debut, fin),
    "des décisions",
  );
}

/** Membres lus avec la session (RLS), e-mails lus en service_role pour ces seuls membres. */
function depotAuteurs(supabase: Supabase): DepotAuteurs {
  return {
    async membresDe(organisationId) {
      const { data, error } = await supabase
        .from("membres")
        .select("user_id")
        .eq("organisation_id", organisationId);
      if (error) console.error("cas : lecture des membres impossible", { code: error.code });
      return (data ?? []).map((m) => m.user_id as string);
    },
    async emailDe(userId) {
      const { data, error } = await creerClientAdmin().auth.admin.getUserById(userId);
      if (error) console.error("cas : lecture d'un auteur impossible", { code: error.code });
      return data.user?.email ?? null;
    },
  };
}

const nombre = (n: number) => n.toLocaleString("fr-FR");

function Indices({ titre, indices, pour }: { titre: string; indices: string[]; pour: boolean }) {
  const Icone = pour ? CirclePlus : CircleMinus;
  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-sm font-medium">{titre}</h4>
      {indices.length ? (
        <ul className="flex flex-col gap-1 text-sm">
          {indices.map((indice) => (
            <li key={indice} className="flex gap-2 break-words">
              <Icone aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span className="min-w-0">{indice}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Aucun.</p>
      )}
    </div>
  );
}

export default async function CasDouteux({ params }: PageProps<"/groupes/[id]/cartos/[cartoId]/cas">) {
  const { id, cartoId } = await params;
  if (!z.uuid().safeParse(id).success || !z.uuid().safeParse(cartoId).success) notFound();

  const { supabase, user } = await utilisateurCourant();
  const [{ data: groupe }, { data: carto }] = await Promise.all([
    supabase.from("groupes").select("id, nom").eq("id", id).maybeSingle(),
    supabase
      .from("cartos")
      .select("id, statut, organisation_id")
      .eq("id", cartoId)
      .eq("groupe_id", id)
      .maybeSingle(),
  ]);
  if (!groupe || !carto) notFound();

  const terminee = carto.statut === "terminee";
  const [cas, decisions] = terminee
    ? await Promise.all([lireCas(supabase, cartoId), lireDecisions(supabase, id)])
    : [[] as CasCarto[], [] as DecisionLue[]];
  const dernieres = dernieresDecisions(decisions ?? []);
  const tranches = (cas ?? []).filter((c) => dernieres.has(c.siren)).length;
  const emails = await emailsDesAuteurs(
    depotAuteurs(supabase),
    carto.organisation_id as string,
    [...dernieres.values()].map((d) => (d.decide_par === user.id ? null : d.decide_par)),
  );

  const nomGroupe = groupe.nom as string;
  const lienCarto = `/groupes/${id}/cartos/${cartoId}`;

  return (
    <main className="flex flex-1 flex-col gap-6 px-4 py-8 md:mx-auto md:w-full md:max-w-3xl md:px-8">
      <div className="flex flex-col gap-1">
        <Link href={lienCarto} className={`${LIEN} self-start text-sm break-words`}>
          ← Carto de {nomGroupe}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight break-words">Cas douteux de {nomGroupe}</h1>
      </div>

      <p className="text-sm">
        Le moteur range ici les sociétés qu&apos;il ne peut pas trancher seul : confiance C,
        co-entreprises, participations sans contrôle, sociétés étrangères. Votre décision vaut pour le
        groupe : elle sera reprise à la prochaine carto. Cette carto-ci ne change pas.
      </p>

      {!terminee ? (
        <p className="text-sm">
          Cette carto n&apos;est pas terminée : il n&apos;y a pas encore de cas à trancher.{" "}
          <Link href={lienCarto} className={LIEN}>
            Revenir à la carto
          </Link>
        </p>
      ) : cas === null || decisions === null ? (
        <p role="alert" className="text-sm text-destructive">
          Les cas de cette carto n&apos;ont pas pu être lus. Rechargez la page.
        </p>
      ) : cas.length === 0 ? (
        <p className="text-sm">Aucun cas douteux dans cette carto : rien à trancher.</p>
      ) : (
        <section aria-labelledby="titre-cas" className="flex flex-col gap-4">
          <h2 id="titre-cas" className="text-lg font-medium">
            {nombre(cas.length)} cas, dont {nombre(tranches)} tranché{tranches > 1 ? "s" : ""}
          </h2>
          <ul className="flex flex-col gap-4">
            {cas.map((c) => {
              const designation = c.nom ? `${c.nom} (SIREN ${c.siren})` : `la société ${c.siren}`;
              const derniere = dernieres.get(c.siren);
              const appliquee = estDecision(c.decision) ? c.decision : null;
              const titre = `cas-${c.siren}`;
              return (
                <li key={c.siren}>
                  <article
                    aria-labelledby={titre}
                    className="flex flex-col gap-3 rounded-xl px-4 py-4 text-sm ring-1 ring-foreground/10"
                  >
                    <div className="flex flex-col gap-1">
                      <h3 id={titre} className="text-base font-medium break-words">
                        {c.nom ?? "Société sans nom au registre"}
                      </h3>
                      <p className="text-muted-foreground tabular-nums">SIREN {c.siren}</p>
                      <ul aria-label="Pourquoi ce cas est douteux" className="flex flex-wrap gap-2">
                        {c.types.map((t) => (
                          <li key={t} className="rounded-md border px-2 py-0.5 text-xs font-medium">
                            {libelleType(t)}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <p className="flex gap-2 font-medium">
                      {c.retenue ? (
                        <CircleCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                      ) : (
                        <CircleX aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                      )}
                      {c.retenue ? "Dans cette carto" : "Hors de cette carto"}
                    </p>

                    <div className="flex flex-col gap-1">
                      <h4 className="text-sm font-medium">Règle</h4>
                      <p className="break-words">{c.regle}</p>
                    </div>

                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <Indices titre="Indices pour" indices={c.indices_pour} pour />
                      <Indices titre="Indices contre" indices={c.indices_contre} pour={false} />
                    </div>

                    <div className="flex flex-col gap-1">
                      <h4 className="text-sm font-medium">Décision</h4>
                      <p>
                        {derniere ? decisionFr(derniere, user.id, emails) : "Pas encore de décision."}
                        {appliquee ? ` Appliquée à cette carto : ${LIBELLE_DECISION[appliquee].toLowerCase()}.` : ""}
                      </p>
                    </div>

                    <DecisionCas
                      groupeId={id}
                      cartoId={cartoId}
                      siren={c.siren}
                      designation={designation}
                      enVigueur={derniere && estDecision(derniere.decision) ? derniere.decision : null}
                    />
                  </article>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </main>
  );
}
