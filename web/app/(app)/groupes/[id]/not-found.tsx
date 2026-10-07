// Groupe introuvable (T019) : il n'existe pas, ou il appartient à une autre
// organisation (RLS). Les deux cas ont le même message : on ne révèle rien.
import Link from "next/link";

export default function GroupeIntrouvable() {
  return (
    <main className="flex flex-1 flex-col gap-4 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8">
      <h1 className="text-2xl font-semibold tracking-tight">Groupe introuvable</h1>
      <p className="text-base">
        Ce groupe n&apos;existe pas, ou il n&apos;appartient pas à votre organisation.
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
