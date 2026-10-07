// Nouveau groupe (T019, FR-004) : chercher la société de tête par nom ou par
// SIREN dans le registre, puis la choisir. La recherche passe par le serveur
// (lib/recherche.ts) : le navigateur ne joint jamais le worker.
import type { Metadata } from "next";
import Form from "next/form";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LIBELLES_STATUT, chercherSocietes, type Societe } from "@/lib/recherche";
import { utilisateurCourant } from "@/lib/session";

import { SANS_ORGANISATION, organisationMembre } from "../organisation";
import { ChoixTete } from "./choix-tete";

export const metadata: Metadata = { title: "Nouveau groupe · cartoFR" };

const LIEN =
  "inline-flex min-h-11 items-center font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring rounded-sm";

const PASTILLE: Record<Societe["statut"], string> = {
  active: "border-emerald-700/40 text-emerald-900 dark:text-emerald-200",
  cessee: "border-amber-700/50 text-amber-900 dark:text-amber-200",
  radiee: "border-destructive/50 text-destructive",
};

function Recherche({ q, id, libelle, aide }: { q: string; id: string; libelle: string; aide: string }) {
  return (
    <Form action="/groupes/nouveau" noValidate className="flex flex-col gap-2 md:max-w-xl">
      <Label htmlFor={id}>{libelle}</Label>
      <p id={`${id}-aide`} className="text-sm text-muted-foreground">
        {aide}
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          id={id}
          name="q"
          type="search"
          defaultValue={q}
          autoComplete="off"
          minLength={2}
          maxLength={100}
          required
          aria-describedby={`${id}-aide`}
        />
        <Button type="submit" className="w-full sm:w-auto">
          Chercher
        </Button>
      </div>
    </Form>
  );
}

export default async function NouveauGroupe({ searchParams }: PageProps<"/groupes/nouveau">) {
  const { supabase, user } = await utilisateurCourant();
  const organisationId = await organisationMembre(supabase, user.id);
  const brut = (await searchParams).q;
  const q = (Array.isArray(brut) ? brut[0] : (brut ?? "")).trim();

  if (!organisationId) {
    return (
      <main className="flex flex-1 flex-col gap-4 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
        <h1 className="text-2xl font-semibold tracking-tight">Nouveau groupe</h1>
        <p className="text-base">{SANS_ORGANISATION}</p>
      </main>
    );
  }

  const resultat = q ? await chercherSocietes(q) : null;

  // Têtes qui ont déjà un groupe dans l'organisation : on mène au groupe au
  // lieu de proposer un doublon. Lu avec la session (RLS).
  const dejaGroupes = new Map<string, string>();
  if (resultat?.ok && resultat.societes.length > 0) {
    const { data } = await supabase
      .from("groupes")
      .select("id, tete_siren")
      .eq("organisation_id", organisationId)
      .in(
        "tete_siren",
        resultat.societes.map((s) => s.siren),
      );
    for (const g of data ?? []) dejaGroupes.set(g.tete_siren as string, g.id as string);
  }

  return (
    <main className="flex flex-1 flex-col gap-6 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <div className="flex flex-col gap-1">
        <Link href="/groupes" className={`${LIEN} self-start text-sm`}>
          ← Groupes
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Nouveau groupe</h1>
        <p className="text-sm text-muted-foreground">
          Choisissez la société de tête du groupe : la maison mère, en France.
        </p>
      </div>

      <Recherche
        q={q}
        id="recherche-tete"
        libelle="Nom ou SIREN de la société de tête"
        aide="Par exemple « LVMH » ou « 775670417 ». Au moins 2 caractères."
      />

      {resultat && !resultat.ok ? (
        <p
          role="alert"
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive md:max-w-xl"
        >
          <span className="font-medium">Erreur : </span>
          {resultat.message}
        </p>
      ) : null}

      {resultat?.ok && resultat.societes.length === 0 ? (
        <section aria-labelledby="titre-aucun" className="flex flex-col gap-4 md:max-w-xl">
          <h2 id="titre-aucun" className="text-lg font-medium" role="status">
            Aucune société trouvée
          </h2>
          <p className="text-sm text-muted-foreground">
            Aucune société du registre ne correspond à « {q} ». Vérifiez l&apos;orthographe, essayez
            un nom plus court, ou saisissez directement le SIREN de la société de tête.
          </p>
          <Form action="/groupes/nouveau" noValidate className="flex flex-col gap-2">
            <Label htmlFor="siren-tete">SIREN de la société de tête (9 chiffres)</Label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id="siren-tete"
                name="q"
                inputMode="numeric"
                autoComplete="off"
                pattern="[0-9 ]{9,11}"
                maxLength={11}
                required
                title="9 chiffres, par exemple 775670417"
              />
              <Button type="submit" variant="outline" className="w-full sm:w-auto">
                Chercher ce SIREN
              </Button>
            </div>
          </Form>
        </section>
      ) : null}

      {resultat?.ok && resultat.societes.length > 0 ? (
        <section aria-labelledby="titre-resultats" className="flex flex-col gap-3">
          <h2 id="titre-resultats" className="text-lg font-medium" role="status">
            {resultat.societes.length}{" "}
            {resultat.societes.length > 1 ? "sociétés trouvées" : "société trouvée"}
            {resultat.societes.length === 20 ? " (les 20 premières : précisez si besoin)" : ""}
          </h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {resultat.societes.map((s) => {
              const groupeId = dejaGroupes.get(s.siren);
              return (
                <li key={s.siren} className="flex min-w-0 flex-col gap-3 rounded-xl border p-4">
                  <div className="flex min-w-0 flex-col gap-1">
                    <p className="font-medium break-words">
                      {s.nom}
                      {s.sigle ? <span className="text-muted-foreground"> ({s.sigle})</span> : null}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      SIREN <span className="font-mono tabular-nums">{s.siren}</span>
                      {" · "}
                      {s.ville ?? "Ville inconnue"}
                    </p>
                    <p>
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${PASTILLE[s.statut]}`}
                      >
                        {LIBELLES_STATUT[s.statut]}
                      </span>
                    </p>
                  </div>
                  {groupeId ? (
                    <p className="text-sm">
                      Déjà un groupe de votre organisation.{" "}
                      <Link href={`/groupes/${groupeId}`} className={LIEN}>
                        Ouvrir le groupe
                      </Link>
                    </p>
                  ) : (
                    <ChoixTete
                      siren={s.siren}
                      nom={s.nom}
                      inactive={s.statut === "active" ? null : LIBELLES_STATUT[s.statut]}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
