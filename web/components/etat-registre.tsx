// État du registre (T014) : une carte par source et un bandeau si les données
// ont plus de 7 jours (PRD SC-003). Le statut est toujours écrit en toutes
// lettres avec une icône : la couleur ne porte jamais seule le sens.
import {
  CircleCheck,
  CircleHelp,
  Hourglass,
  OctagonAlert,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import {
  FRAICHEUR_MAX_JOURS,
  etatsAffiches,
  fraicheur,
  type LigneEtatRegistre,
  type Ton,
} from "@/lib/etat-registre";

const ICONES: Record<Ton, LucideIcon> = {
  succes: CircleCheck,
  en_cours: Hourglass,
  attention: TriangleAlert,
  echec: OctagonAlert,
  inconnu: CircleHelp,
};

// Couleurs en complément du texte, contrastées AA sur fond clair et sombre.
const TONS: Record<Ton, string> = {
  succes: "border-emerald-700/40 text-emerald-800 dark:text-emerald-300",
  en_cours: "border-sky-700/40 text-sky-800 dark:text-sky-300",
  attention: "border-amber-700/40 text-amber-900 dark:text-amber-300",
  echec: "border-red-700/40 text-red-800 dark:text-red-300",
  inconnu: "border-foreground/30 text-foreground",
};

function Bandeau({ lignes, maintenant }: { lignes: readonly LigneEtatRegistre[]; maintenant: Date }) {
  const f = fraicheur(lignes, maintenant);
  if (f.etat === "a_jour") return null;
  const message =
    f.etat === "inconnue"
      ? "Une source du registre n'a encore jamais été synchronisée : la date des données est inconnue."
      : `Données du registre vieilles de ${f.jours} jours : la cible est ${FRAICHEUR_MAX_JOURS} jours au plus.`;
  return (
    <div
      role="alert"
      className="flex gap-3 rounded-lg border border-amber-700/50 bg-amber-50 px-3 py-3 text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"
    >
      <TriangleAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
      <p className="text-sm">
        <strong className="font-semibold">Attention. </strong>
        {message} Vérifiez que la synchro nocturne tourne (variable{" "}
        <code className="break-words">CARTOFR_SYNCHRO_HEURE</code> du worker).
      </p>
    </div>
  );
}

export function EtatRegistre({
  lignes,
  maintenant,
}: {
  lignes: readonly LigneEtatRegistre[];
  maintenant: Date;
}) {
  const etats = etatsAffiches(lignes);
  return (
    <div className="flex flex-col gap-6">
      <Bandeau lignes={lignes} maintenant={maintenant} />
      <ul className="grid gap-4 md:grid-cols-2">
        {etats.map((e) => {
          const Icone = ICONES[e.statut.ton];
          const idTitre = `source-${e.code}`;
          return (
            <li key={e.code} className="flex flex-col gap-4 rounded-xl border p-4">
              <h2 id={idTitre} className="text-base font-medium">
                {e.libelle}
              </h2>
              <p
                className={`inline-flex w-fit items-center gap-2 rounded-lg border px-2 py-1 text-sm font-medium ${TONS[e.statut.ton]}`}
              >
                <Icone aria-hidden="true" className="size-4 shrink-0" />
                <span>
                  <span className="sr-only">Statut : </span>
                  {e.statut.texte}
                </span>
              </p>
              <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
                <dt className="text-muted-foreground">Date des données</dt>
                <dd className="mb-2 sm:mb-0">{e.dateDonnees ?? "Aucune"}</dd>
                <dt className="text-muted-foreground">Dernier passage</dt>
                <dd>{e.dernierPassage ?? "Jamais"}</dd>
              </dl>
              {e.erreur ? (
                <div className="rounded-lg border border-red-700/40 px-3 py-2 text-sm">
                  <p className="font-medium">
                    Échec du passage du {e.dernierPassage ?? "(date inconnue)"}
                  </p>
                  <p className="break-words">Cause : {e.erreur}</p>
                </div>
              ) : null}
              {e.volumes.length > 0 ? (
                <details className="text-sm">
                  <summary className="min-h-11 cursor-pointer content-center rounded-lg outline-none focus-visible:ring-3 focus-visible:ring-ring">
                    Volumes du dernier passage
                  </summary>
                  <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
                    {e.volumes.map((v) => (
                      <div key={v.libelle} className="contents">
                        <dt className="text-muted-foreground">{v.libelle}</dt>
                        <dd className="text-right tabular-nums">{v.valeur}</dd>
                      </div>
                    ))}
                  </dl>
                </details>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
