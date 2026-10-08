"use client";

// Les deux boutons d'un cas douteux, « Retenir » et « Écarter » (T028).
// Le droit de décider se vérifie côté serveur (cas/actions.ts) ; ici, les
// boutons envoient la décision et disent ce qui s'est passé. Le bouton de la
// décision en vigueur est marqué enfoncé (aria-pressed), en texte aussi.
import { Check, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import type { Decision, Resultat } from "@/lib/cartos/cas";

import { deciderCas } from "./actions";

type Props = {
  groupeId: string;
  cartoId: string;
  siren: string;
  /** Nom de la société, ou son SIREN : complète le libellé des boutons pour un lecteur d'écran. */
  designation: string;
  /** La dernière décision enregistrée sur cette société, ou null. */
  enVigueur: Decision | null;
};

export function DecisionCas({ groupeId, cartoId, siren, designation, enVigueur }: Props) {
  const router = useRouter();
  const [resultat, setResultat] = useState<Resultat | null>(null);
  const [enCours, demarrer] = useTransition();
  const actuelle = resultat?.statut === "ok" ? resultat.decision : enVigueur;

  function decider(decision: Decision) {
    demarrer(async () => {
      const r = await deciderCas({ groupeId, cartoId, siren, decision });
      setResultat(r);
      if (r.statut === "ok") router.refresh();
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-2 sm:flex-row" role="group" aria-label={`Décision pour ${designation}`}>
        <Button
          type="button"
          variant={actuelle === "retenir" ? "default" : "outline"}
          aria-pressed={actuelle === "retenir"}
          aria-label={`Retenir ${designation} dans le groupe`}
          disabled={enCours}
          onClick={() => decider("retenir")}
          className="w-full sm:w-auto"
        >
          <Check aria-hidden="true" />
          Retenir
        </Button>
        <Button
          type="button"
          variant={actuelle === "ecarter" ? "default" : "outline"}
          aria-pressed={actuelle === "ecarter"}
          aria-label={`Écarter ${designation} du groupe`}
          disabled={enCours}
          onClick={() => decider("ecarter")}
          className="w-full sm:w-auto"
        >
          <X aria-hidden="true" />
          Écarter
        </Button>
      </div>
      <div aria-live="polite" className="empty:hidden">
        {enCours ? (
          <p className="text-sm text-muted-foreground">Enregistrement…</p>
        ) : resultat?.statut === "erreur" ? (
          <p
            role="alert"
            className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            <span className="font-medium">Erreur : </span>
            {resultat.message}
          </p>
        ) : resultat?.statut === "ok" ? (
          <p className="text-sm">{resultat.message}</p>
        ) : null}
      </div>
    </div>
  );
}
