// Réglages d'un groupe : la dernière version, sa saisie, sa validation et
// l'historique (T020, FR-005, US2 scénarios 2 et 5).
//
// Tout est lu avec la session de l'utilisateur : RLS limite aux groupes de
// ses organisations, un autre groupe rend une page introuvable. Les familles
// exclues ne s'affichent que par leur nombre (garde-fou 6) : ni nom, ni
// empreinte n'est envoyé au navigateur.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";

import { LISTES } from "@/lib/reglages/schema";
import { utilisateurCourant } from "@/lib/session";

import { EditeurReglages } from "./editeur-reglages";

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
};

export default async function PageReglages(props: PageProps<"/groupes/[id]/reglages">) {
  const { id } = await props.params;
  if (!z.uuid().safeParse(id).success) notFound();

  const { supabase, user } = await utilisateurCourant();
  const [{ data: groupe }, { data: versions }] = await Promise.all([
    supabase.from("groupes").select("id, nom, tete_siren").eq("id", id).maybeSingle(),
    supabase
      .from("reglages")
      .select("id, version, origine, contenu, cree_le, cree_par, valide_le, valide_par")
      .eq("groupe_id", id)
      .order("version", { ascending: false }),
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

  function etat(v: LigneVersion): string {
    if (v.valide_le) {
      if (v.origine === "depart") return `Réglages de départ (repris du prototype), validés ${quand(v.valide_le)}`;
      const par = qui(v.valide_par);
      return `Validée ${quand(v.valide_le)}${par ? ` par ${par}` : " (compte effacé)"}`;
    }
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

      <EditeurReglages
        groupeId={groupe.id as string}
        baseVersion={derniere?.version ?? 0}
        aValider={derniere !== null && !derniere.valide_le}
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
                  Version {v.version} · {v.valide_le ? "validée" : "brouillon"}
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
