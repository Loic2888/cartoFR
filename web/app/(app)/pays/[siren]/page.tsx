// Carto d'une société dans la carto du pays (T050, US2, FR-007) : la société
// et tout ce qui descend d'elle en France, déjà calculée chaque nuit (T048).
// Aucun calcul à attendre : la page lit la route `/groupe` du worker.
//
// Jamais les autres filiales de sa mère ou de ses actionnaires (décidé le
// 2026-10-18) : sa mère est nommée au-dessus, avec un lien vers sa carto. Une
// mère entrepreneur individuel est dite « personne physique, non affichée »,
// sans lien (garde-fou 6). La carto du pays est commune à toutes les
// organisations ; seul le lien vers une carto corrigée est lu avec la session
// (RLS) et ne montre que celles de l'organisation.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Arbre } from "@/components/arbre/arbre";
import { buttonVariants } from "@/components/ui/button";
import { construireArbre } from "@/lib/cartos/arbre";
import { lireCartoPays } from "@/lib/pays";
import { utilisateurCourant } from "@/lib/session";

import { organisationMembre } from "../../groupes/organisation";
import { type Correction, EnTete, nomAffiche } from "./en-tete";

export const metadata: Metadata = { title: "Carto · cartoFR" };

const LIEN =
  "inline-flex min-h-11 items-center rounded-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring";

type Supabase = Awaited<ReturnType<typeof utilisateurCourant>>["supabase"];

/** La dernière carto terminée d'un groupe de l'organisation dont la tête est ce SIREN. */
async function lireCorrection(supabase: Supabase, organisationId: string, siren: string): Promise<Correction> {
  const { data: groupes, error } = await supabase
    .from("groupes")
    .select("id")
    .eq("organisation_id", organisationId)
    .eq("tete_siren", siren);
  if (error || !groupes || groupes.length === 0) return null;
  const { data: carto } = await supabase
    .from("cartos")
    .select("id, groupe_id")
    .in(
      "groupe_id",
      groupes.map((g) => g.id as string),
    )
    .eq("statut", "terminee")
    .order("cree_le", { ascending: false })
    .limit(1)
    .maybeSingle();
  return carto ? { groupeId: carto.groupe_id as string, cartoId: carto.id as string } : null;
}

export default async function CartoPays({ params }: PageProps<"/pays/[siren]">) {
  const { siren } = await params;
  if (!/^[0-9]{9}$/.test(siren)) notFound();

  const { supabase, user } = await utilisateurCourant();
  const [resultat, organisationId] = await Promise.all([lireCartoPays(siren), organisationMembre(supabase, user.id)]);
  if (!resultat.ok && resultat.introuvable) notFound();

  if (!resultat.ok) {
    return (
      <main className="flex flex-1 flex-col gap-4 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
        <Link href="/" className={`${LIEN} self-start text-sm`}>
          ← Accueil
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Carto indisponible</h1>
        <p
          role="alert"
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive md:max-w-xl"
        >
          <span className="font-medium">Erreur : </span>
          {resultat.message}
        </p>
      </main>
    );
  }

  const { carto } = resultat;
  const correction = organisationId ? await lireCorrection(supabase, organisationId, siren) : null;
  const nom = nomAffiche(carto);

  return (
    <main className="flex flex-1 flex-col gap-6 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <Link href="/" className={`${LIEN} self-start text-sm`}>
        ← Accueil
      </Link>

      <EnTete carto={carto} correction={correction} />

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {/* Fichier rendu par une route : un lien ordinaire, pas une navigation client. */}
        <a href={`/pays/${siren}/export`} className={buttonVariants({ className: "min-h-11 w-full sm:w-auto" })}>
          Exporter (CSV)
        </a>
      </div>

      <section aria-labelledby="titre-arbre" className="flex flex-col gap-4">
        <h2 id="titre-arbre" className="text-lg font-medium">
          Arbre de {nom}
        </h2>
        <Arbre racines={construireArbre(carto.societes)} libelle={`Arbre de ${nom}`} />
      </section>
    </main>
  );
}
