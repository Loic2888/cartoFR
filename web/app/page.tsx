// Page d'accueil provisoire : remplacée par le parcours de connexion (T009).
export default function Accueil() {
  return (
    <main className="flex flex-1 flex-col gap-4 px-4 py-8 md:mx-auto md:max-w-3xl md:px-8 md:py-16">
      <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">cartoFR</h1>
      <p className="text-base text-muted-foreground">
        Cartographie des groupes d&apos;entreprises françaises : maison mère, filiales et
        sous-filiales, avec la preuve de chaque lien.
      </p>
      <p className="text-sm text-muted-foreground">Application en construction.</p>
    </main>
  );
}
