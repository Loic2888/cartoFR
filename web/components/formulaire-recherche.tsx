// Formulaire de recherche d'une société par nom ou par SIREN (T019, T050) :
// une navigation GET vers `action?q=…`, rendue par le serveur. Partagé par
// l'accueil et l'écran « Nouveau groupe ».
import Form from "next/form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  action: string;
  q: string;
  id: string;
  libelle: string;
  aide: string;
};

export function FormulaireRecherche({ action, q, id, libelle, aide }: Props) {
  return (
    <Form action={action} noValidate className="flex flex-col gap-2 md:max-w-xl">
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
