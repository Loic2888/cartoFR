// Gabarit des pages connectées (T009) : en-tête, navigation, déconnexion.
// Mobile d'abord : à 320 px, les liens passent sous le nom de l'app, chaque
// cible fait 44 px de haut, rien ne déborde.
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { organisationAdministree, utilisateurCourant } from "@/lib/session";

import { deconnecter } from "./actions";

const LIEN =
  "inline-flex min-h-11 items-center rounded-lg px-3 text-sm font-medium outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring";

export default async function GabaritApp({ children }: LayoutProps<"/">) {
  const { supabase, user } = await utilisateurCourant();
  const estAdmin = (await organisationAdministree(supabase, user.id)) !== null;

  return (
    <>
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 md:px-8">
          <Link href="/" className={`${LIEN} -ml-3 text-base font-semibold`}>
            cartoFR
          </Link>
          <nav aria-label="Navigation principale" className="order-last w-full md:order-none md:w-auto">
            <ul className="-ml-3 flex flex-wrap gap-1">
              <li>
                <Link href="/" className={LIEN}>
                  Accueil
                </Link>
              </li>
              {estAdmin ? (
                <li>
                  <Link href="/admin/membres" className={LIEN}>
                    Membres
                  </Link>
                </li>
              ) : null}
            </ul>
          </nav>
          <form action={deconnecter} className="ml-auto">
            <Button type="submit" variant="outline">
              Se déconnecter
            </Button>
          </form>
        </div>
      </header>
      {children}
    </>
  );
}
