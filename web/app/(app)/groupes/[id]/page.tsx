// Fiche d'un groupe (T019) : sa tête, sa date de création, et le lien vers ses
// réglages (T020). Lu avec la session (RLS) : un groupe d'une autre
// organisation n'existe pas pour l'utilisateur, d'où un 404.
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { z } from "zod";

import { buttonVariants } from "@/components/ui/button";
import { utilisateurCourant } from "@/lib/session";

import { dateFr } from "../organisation";

export const metadata: Metadata = { title: "Groupe · cartoFR" };

export default async function Groupe({ params }: PageProps<"/groupes/[id]">) {
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) notFound();

  const { supabase } = await utilisateurCourant();
  const { data: groupe } = await supabase
    .from("groupes")
    .select("id, nom, tete_siren, cree_le")
    .eq("id", id)
    .maybeSingle();
  if (!groupe) notFound();

  return (
    <main className="flex flex-1 flex-col gap-6 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <div className="flex flex-col gap-1">
        <Link
          href="/groupes"
          className="inline-flex min-h-11 items-center self-start rounded-sm text-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring"
        >
          ← Groupes
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight break-words">{groupe.nom as string}</h1>
      </div>

      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="text-muted-foreground">SIREN de la tête</dt>
        <dd className="font-mono tabular-nums">{groupe.tete_siren as string}</dd>
        <dt className="text-muted-foreground">Créé le</dt>
        <dd>{dateFr.format(new Date(groupe.cree_le as string))}</dd>
      </dl>

      <div>
        <Link
          href={`/groupes/${groupe.id as string}/reglages`}
          className={buttonVariants({ className: "w-full sm:w-auto" })}
        >
          Réglages
        </Link>
      </div>
    </main>
  );
}
