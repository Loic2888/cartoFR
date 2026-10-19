// Accueil (T050, US2) : chercher une société par nom ou par SIREN, et ouvrir sa
// carto, déjà calculée dans la carto du pays. Chaque résultat dit dans quel
// groupe la société est rangée et la taille de ce groupe. La recherche passe
// par le serveur (lib/recherche.ts) : le navigateur ne joint jamais le worker.
import type { Metadata } from "next";
import Link from "next/link";

import { FormulaireRecherche } from "@/components/formulaire-recherche";
import { sirenFr } from "@/lib/cartos/arbre";
import { LIBELLES_STATUT, chercherSocietes, type Societe } from "@/lib/recherche";
import { utilisateurCourant } from "@/lib/session";

export const metadata: Metadata = { title: "Accueil · cartoFR" };

const LIEN =
  "inline-flex min-h-11 items-center rounded-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring";

function Groupe({ societe }: { societe: Societe }) {
  const g = societe.groupe;
  if (!g) return <p className="text-sm text-muted-foreground">Sans groupe : société seule.</p>;
  const nom = g.nom ?? `SIREN ${sirenFr(g.tete)}`;
  const taille = `${g.taille.toLocaleString("fr-FR")} ${g.taille > 1 ? "sociétés" : "société"}`;
  return (
    <p className="text-sm break-words">
      {g.tete === societe.siren ? `Tête du groupe ${nom}` : `Groupe ${nom}`} · {taille}
    </p>
  );
}

export default async function Accueil({ searchParams }: PageProps<"/">) {
  // Chaque page revérifie la session, sans s'en remettre au proxy ni au layout.
  await utilisateurCourant();
  const brut = (await searchParams).q;
  const q = (Array.isArray(brut) ? brut[0] : (brut ?? "")).trim();
  const resultat = q ? await chercherSocietes(q) : null;

  return (
    <main className="flex flex-1 flex-col gap-6 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8 md:py-12">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Carto d&apos;une société</h1>
        <p className="text-base text-muted-foreground">
          La société, ses filiales et sous-filiales en France, avec la preuve de chaque lien. Toutes les
          cartos sont déjà calculées : rien à attendre.
        </p>
      </div>

      <FormulaireRecherche
        action="/"
        q={q}
        id="recherche-societe"
        libelle="Nom ou SIREN de la société"
        aide="Par exemple « VINCI » ou « 552037806 ». Au moins 2 caractères."
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
        <p className="text-sm md:max-w-xl" role="status">
          Aucune société du registre ne correspond à « {q} ». Vérifiez l&apos;orthographe, essayez un nom
          plus court, ou saisissez le SIREN.
        </p>
      ) : null}

      {resultat?.ok && resultat.societes.length > 0 ? (
        <section aria-labelledby="titre-resultats" className="flex flex-col gap-3">
          <h2 id="titre-resultats" className="text-lg font-medium" role="status">
            {resultat.societes.length}{" "}
            {resultat.societes.length > 1 ? "sociétés trouvées" : "société trouvée"}
            {resultat.societes.length === 20 ? " (les 20 premières : précisez si besoin)" : ""}
          </h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {resultat.societes.map((s) => (
              <li key={s.siren} className="flex min-w-0 flex-col gap-1 rounded-xl border p-4">
                <p className="font-medium break-words">
                  {s.nom}
                  {s.sigle ? <span className="text-muted-foreground"> ({s.sigle})</span> : null}
                </p>
                <p className="text-sm text-muted-foreground">
                  SIREN <span className="font-mono tabular-nums">{sirenFr(s.siren)}</span>
                  {" · "}
                  {s.ville ?? "Ville inconnue"}
                </p>
                {s.statut === "active" ? (
                  <>
                    <Groupe societe={s} />
                    <Link href={`/pays/${s.siren}`} className={`${LIEN} self-start`}>
                      Voir la carto<span className="sr-only"> de {s.nom}</span>
                    </Link>
                  </>
                ) : (
                  <p className="text-sm">{LIBELLES_STATUT[s.statut]} : pas de carto pour une société fermée.</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
