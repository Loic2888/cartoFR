// Accueil provisoire, derrière la connexion (T009). La recherche d'un groupe
// arrive avec les tâches de l'US1.
export default function Accueil() {
  return (
    <main className="flex flex-1 flex-col gap-4 px-4 py-8 md:mx-auto md:w-full md:max-w-5xl md:px-8 md:py-16">
      <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">cartoFR</h1>
      <p className="text-base text-muted-foreground">
        Cartographie des groupes d&apos;entreprises françaises : maison mère, filiales et
        sous-filiales, avec la preuve de chaque lien.
      </p>
      <p className="text-sm text-muted-foreground">Application en construction.</p>
    </main>
  );
}
