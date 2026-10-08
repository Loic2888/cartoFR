// Réglages d'un groupe : la dernière version, sa saisie, sa validation et
// l'historique (T020, FR-005, US2 scénarios 2 et 5) ; la proposition de l'IA
// et sa revue (T026, FR-008, SC-007).
//
// Tout est lu avec la session de l'utilisateur : RLS limite aux groupes de
// ses organisations, un autre groupe rend une page introuvable. Les familles
// exclues ne s'affichent que par leur nombre (garde-fou 6) : ni nom, ni
// empreinte n'est envoyé au navigateur.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";

import { lireDernierTravail } from "@/lib/reglages/depot-proposition";
import { etatTravail, lireElements, propositionEnCours } from "@/lib/reglages/proposition";
import { LISTES } from "@/lib/reglages/schema";
import { utilisateurCourant } from "@/lib/session";

import { EditeurReglages } from "./editeur-reglages";
import { DemandeProposition, RevueProposition } from "./proposition";

export const metadata: Metadata = { title: "Réglages · cartoFR" };

const jour = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "Europe/Paris",
});
const heure = new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Paris",
});

function quand(iso: string): string {
  const d = new Date(iso);
  return `le ${jour.format(d)} à ${heure.format(d)}`;
}

type LigneVersion = {
  id: string;
  version: number;
  origine: string;
  contenu: Record<string, unknown>;
  cree_le: string;
  cree_par: string | null;
  valide_le: string | null;
  valide_par: string | null;
  proposition: unknown;
  corrections: number | null;
};

export default async function PageReglages(props: PageProps<"/groupes/[id]/reglages">) {
  const { id } = await props.params;
  if (!z.uuid().safeParse(id).success) notFound();

  const { supabase, user } = await utilisateurCourant();
  const [{ data: groupe }, { data: versions }, travail] = await Promise.all([
    supabase.from("groupes").select("id, nom, tete_siren").eq("id", id).maybeSingle(),
    supabase
      .from("reglages")
      .select("id, version, origine, contenu, cree_le, cree_par, valide_le, valide_par, proposition, corrections")
      .eq("groupe_id", id)
      .order("version", { ascending: false }),
    lireDernierTravail(supabase, id),
  ]);
  if (!groupe) notFound();

  const lignes = (versions ?? []) as LigneVersion[];
  const derniere = lignes[0] ?? null;
  // Qui : « vous » ou « un membre ». Ni nom ni e-mail (minimisation).
  const qui = (userId: string | null) =>
    userId === null ? null : userId === user.id ? "vous" : "un membre";

  const listes = Object.fromEntries(
    LISTES.map((l) => {
      const valeurs = derniere?.contenu[l.cle];
      return [l.cle, Array.isArray(valeurs) ? valeurs.map(String).join("\n") : ""];
    }),
  ) as Record<(typeof LISTES)[number]["cle"], string>;
  const empreintes = derniere?.contenu.familles_exclues_empreintes;
  const nbFamilles = Array.isArray(empreintes) ? empreintes.length : 0;
  // La dernière version est une proposition de l'IA : elle se revoit, elle ne
  // se valide pas telle quelle (migration 0004, principe 1).
  const aRevoir = derniere !== null && derniere.origine === "proposition" && !derniere.valide_le;
  const elements = aRevoir ? lireElements(derniere.proposition) : null;

  function etat(v: LigneVersion): string {
    if (v.valide_le) {
      if (v.origine === "depart") return `Réglages de départ (repris du prototype), validés ${quand(v.valide_le)}`;
      const par = qui(v.valide_par);
      const revue =
        v.corrections === null
          ? ""
          : `, après revue d'une proposition de l'IA (${v.corrections === 0 ? "aucune correction" : v.corrections === 1 ? "1 correction" : `${v.corrections} corrections`})`;
      return `Validée ${quand(v.valide_le)}${par ? ` par ${par}` : " (compte effacé)"}${revue}`;
    }
    if (v.origine === "proposition") return "Proposition de l'IA : à revoir, jamais utilisée telle quelle";
    return "Brouillon : à valider avant de servir aux cartos";
  }

  function creation(v: LigneVersion): string {
    const par = qui(v.cree_par);
    return `Créée ${quand(v.cree_le)}${par ? ` par ${par}` : ""}`;
  }

  return (
    <main className="flex flex-1 flex-col gap-8 px-4 py-8 md:mx-auto md:w-full md:max-w-3xl md:px-8">
      <div className="flex flex-col gap-1">
        <Link
          href={`/groupes/${groupe.id as string}`}
          className="-ml-3 inline-flex min-h-11 items-center self-start rounded-lg px-3 text-sm text-muted-foreground underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring"
        >
          Retour au groupe
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight break-words">
          Réglages · {groupe.nom as string}
        </h1>
        <p className="text-sm text-muted-foreground">
          Tête du groupe : SIREN {groupe.tete_siren as string}
        </p>
      </div>

      <section aria-labelledby="titre-version" className="flex flex-col gap-2 rounded-lg border px-4 py-3">
        <h2 id="titre-version" className="text-lg font-medium">
          {derniere ? `Version ${derniere.version}` : "Aucune version"}
        </h2>
        {derniere ? (
          <>
            <p className="text-sm font-medium">{etat(derniere)}</p>
            <p className="text-sm text-muted-foreground">{creation(derniere)}</p>
          </>
        ) : (
          <p className="text-sm">
            Ce groupe n&apos;a pas encore de réglages. Saisissez-les ci-dessous, enregistrez, puis
            validez : le moteur ne tourne que sur une version validée.
          </p>
        )}
      </section>

      <DemandeProposition
        groupeId={groupe.id as string}
        etat={etatTravail(travail, derniere?.cree_le ?? null)}
        enCours={propositionEnCours(travail)}
      />

      {aRevoir ? (
        elements ? (
          <RevueProposition
            key={derniere.id}
            groupeId={groupe.id as string}
            version={derniere.version}
            elements={elements}
            contenu={derniere.contenu}
          />
        ) : (
          <p role="alert" className="rounded-lg border px-3 py-2 text-sm">
            Cette proposition est illisible. Demandez-en une nouvelle.
          </p>
        )
      ) : null}

      <EditeurReglages
        groupeId={groupe.id as string}
        baseVersion={derniere?.version ?? 0}
        aValider={derniere !== null && !derniere.valide_le && !aRevoir}
        listes={listes}
        nbFamilles={nbFamilles}
      />

      {lignes.length > 0 ? (
        <section aria-labelledby="titre-historique" className="flex flex-col gap-4">
          <h2 id="titre-historique" className="text-lg font-medium">
            Historique des versions
          </h2>
          <ol className="flex flex-col gap-2">
            {lignes.map((v) => (
              <li key={v.id} className="flex flex-col gap-1 rounded-lg border px-3 py-2">
                <span className="font-medium">
                  Version {v.version} ·{" "}
                  {v.valide_le ? "validée" : v.origine === "proposition" ? "proposition de l'IA" : "brouillon"}
                </span>
                <span className="text-sm text-muted-foreground">{etat(v)}</span>
                <span className="text-sm text-muted-foreground">{creation(v)}</span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </main>
  );
}
