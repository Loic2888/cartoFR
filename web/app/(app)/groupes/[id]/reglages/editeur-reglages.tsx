"use client";

// Saisie des réglages et validation de la dernière version (T020).
// Une colonne, cibles de 44 px, un <label> par champ (C3), tout au clavier.
// Les noms de famille saisis partent au serveur, qui n'en garde que
// l'empreinte : ils ne reviennent jamais à l'écran (garde-fou 6).
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { Resultat } from "@/lib/reglages/operations";
import { type CleListe, LISTES } from "@/lib/reglages/schema";

import { enregistrerBrouillon, validerVersion } from "./actions";

type Props = {
  groupeId: string;
  baseVersion: number;
  aValider: boolean;
  listes: Record<CleListe, string>;
  nbFamilles: number;
};

const CHAMP =
  "w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-2 text-base outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring md:text-sm dark:bg-input/30";

function compter(texte: string): number {
  return texte.split(/\r\n|\r|\n/).filter((l) => l.trim()).length;
}

function familles(n: number): string {
  return n === 0 ? "Aucune famille exclue" : n === 1 ? "1 famille exclue" : `${n} familles exclues`;
}

function Message({ resultat }: { resultat: Resultat | null }) {
  if (!resultat) return null;
  if (resultat.statut === "erreur") {
    return (
      <p
        role="alert"
        className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
      >
        <span className="font-medium">Erreur : </span>
        {resultat.message}
      </p>
    );
  }
  return <p className="rounded-lg border px-3 py-2 text-sm">{resultat.message}</p>;
}

export function EditeurReglages(props: Props) {
  // Le message survit au remontage du formulaire après un enregistrement.
  const [resultat, setResultat] = useState<Resultat | null>(null);

  return (
    <div className="flex flex-col gap-8">
      {/* Vide, la zone sort du flux sans quitter l'arbre d'accessibilité. */}
      <div id="reglages-etat" aria-live="polite" className="empty:absolute">
        <Message resultat={resultat} />
      </div>
      {props.aValider ? (
        <Validation groupeId={props.groupeId} version={props.baseVersion} onResultat={setResultat} />
      ) : null}
      {/* Une nouvelle version remonte le formulaire : il repart de ce que le
          serveur a enregistré, et le champ des familles se vide. */}
      <Formulaire key={props.baseVersion} {...props} onResultat={setResultat} />
    </div>
  );
}

function Validation({
  groupeId,
  version,
  onResultat,
}: {
  groupeId: string;
  version: number;
  onResultat: (r: Resultat) => void;
}) {
  const [enCours, demarrer] = useTransition();
  return (
    <section aria-labelledby="titre-valider" className="flex flex-col gap-2 rounded-lg border px-4 py-3">
      <h2 id="titre-valider" className="text-lg font-medium">
        Valider la version {version}
      </h2>
      <p className="text-sm text-muted-foreground">
        Relisez les réglages ci-dessous. Une fois validée, la version ne change plus et sert aux
        prochaines cartos.
      </p>
      <Button
        type="button"
        disabled={enCours}
        className="w-full md:w-auto md:self-start"
        onClick={() =>
          demarrer(async () => {
            onResultat(await validerVersion({ groupeId, version }));
          })
        }
      >
        {enCours ? "Validation en cours…" : `Valider la version ${version}`}
      </Button>
    </section>
  );
}

function Formulaire({
  groupeId,
  baseVersion,
  listes: initiales,
  nbFamilles,
  onResultat,
}: Props & { onResultat: (r: Resultat) => void }) {
  const [listes, setListes] = useState(initiales);
  const [famillesAjoutees, setFamillesAjoutees] = useState("");
  const [retirerFamilles, setRetirerFamilles] = useState(false);
  const [enCours, demarrer] = useTransition();

  function enregistrer(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    demarrer(async () => {
      onResultat(
        await enregistrerBrouillon({ groupeId, baseVersion, listes, famillesAjoutees, retirerFamilles }),
      );
    });
  }

  return (
    <form onSubmit={enregistrer} className="flex flex-col gap-6" aria-labelledby="titre-saisie">
      <h2 id="titre-saisie" className="text-lg font-medium">
        Modifier les réglages
      </h2>
      <p className="text-sm text-muted-foreground">
        Une valeur par ligne. Enregistrer crée une nouvelle version en brouillon ; les versions
        précédentes sont conservées.
      </p>

      {LISTES.map((l) => {
        const id = `reglage-${l.cle}`;
        const n = compter(listes[l.cle]);
        return (
          <div key={l.cle} className="flex flex-col gap-2">
            <Label htmlFor={id}>{l.libelle}</Label>
            <p id={`${id}-aide`} className="text-sm text-muted-foreground">
              {l.aide} {n === 0 ? "Aucune valeur." : n === 1 ? "1 valeur." : `${n} valeurs.`}
            </p>
            <textarea
              id={id}
              name={l.cle}
              value={listes[l.cle]}
              onChange={(e) => setListes({ ...listes, [l.cle]: e.target.value })}
              rows={Math.min(Math.max(n + 1, 3), 12)}
              spellCheck={false}
              autoComplete="off"
              inputMode={l.siren ? "numeric" : "text"}
              aria-describedby={`${id}-aide`}
              className={CHAMP}
            />
          </div>
        );
      })}

      <fieldset className="flex flex-col gap-3 rounded-lg border px-4 py-3">
        <legend className="px-1 text-sm font-medium">Familles exclues</legend>
        <p className="text-sm">
          <span className="font-medium">{familles(nbFamilles)}.</span>{" "}
          <span className="text-muted-foreground">
            Leurs holdings personnelles n&apos;entrent jamais dans la carto. Les noms ne sont pas
            conservés : le serveur n&apos;en garde qu&apos;une empreinte, et ils ne s&apos;affichent
            plus ensuite.
          </span>
        </p>
        <div className="flex flex-col gap-2">
          <Label htmlFor="reglage-familles">Ajouter des familles à exclure (une par ligne)</Label>
          <textarea
            id="reglage-familles"
            name="familles_ajoutees"
            value={famillesAjoutees}
            onChange={(e) => setFamillesAjoutees(e.target.value)}
            rows={2}
            spellCheck={false}
            autoComplete="off"
            className={CHAMP}
          />
        </div>
        {nbFamilles > 0 ? (
          <div className="flex min-h-11 items-center gap-3">
            <input
              id="reglage-retirer-familles"
              type="checkbox"
              checked={retirerFamilles}
              onChange={(e) => setRetirerFamilles(e.target.checked)}
              className="size-5 shrink-0 accent-primary outline-none focus-visible:ring-3 focus-visible:ring-ring"
            />
            <Label htmlFor="reglage-retirer-familles" className="font-normal">
              Retirer toutes les familles exclues ({nbFamilles})
            </Label>
          </div>
        ) : null}
      </fieldset>

      <Button type="submit" disabled={enCours} className="w-full md:w-auto md:self-start">
        {enCours ? "Enregistrement en cours…" : "Enregistrer le brouillon"}
      </Button>
    </form>
  );
}
