// Carto introuvable (T022) : elle n'existe pas, n'est pas de ce groupe, ou
// appartient à une autre organisation (RLS). Même message dans tous les cas :
// on ne révèle rien.
import Link from "next/link";

export default function CartoIntrouvable() {
  return (
    <main className="flex flex-1 flex-col gap-4 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <h1 className="text-2xl font-semibold tracking-tight">Carto introuvable</h1>
      <p className="text-base">
        Cette carto n&apos;existe pas, ou elle n&apos;appartient pas à votre organisation.
      </p>
      <Link
        href="/groupes"
        className="inline-flex min-h-11 items-center self-start rounded-sm font-medium underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring"
      >
        Revenir à la liste des groupes
      </Link>
    </main>
  );
}
