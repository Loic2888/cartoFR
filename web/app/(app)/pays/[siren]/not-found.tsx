// Société introuvable (T050) : SIREN mal formé, inconnu du registre, fermé, ou
// d'un entrepreneur individuel (jamais affiché, garde-fou 6). Même message dans
// tous les cas.
import Link from "next/link";

export default function SocieteIntrouvable() {
  return (
    <main className="flex flex-1 flex-col gap-4 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <h1 className="text-2xl font-semibold tracking-tight">Société introuvable</h1>
      <p className="text-base">Aucune société active ne porte ce SIREN dans le registre.</p>
      <Link
        href="/"
        className="inline-flex min-h-11 items-center self-start rounded-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring"
      >
        Chercher une autre société
      </Link>
    </main>
  );
}
