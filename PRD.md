# PRD — cartoFR

Date : 2026-10-06, révisé le 2026-10-16 (carto du pays). Sources : `rapportSaaS.md` (vision), `rapport.md` (résultats du prototype, mesures du 2026-10-14 au 2026-10-16).

## Vision produit

**Le problème**
Pour une mission, un consultant Youno doit connaître toutes les sociétés françaises d'un groupe client : la maison mère, les filiales et les sous-filiales. La carto Cargo actuelle cherche sur le web, société par société, et n'en trouve qu'une sur 4 à une sur 9 (19 sociétés pour LVMH, contre 172 chez Basile). Basile fait mieux, mais à la main, sans donner les liens entre sociétés et sans la preuve de chaque lien.

**La solution**
L'app tient sa propre copie du registre français (SIRENE et RNE), avec tous les liens « société A dirige société B », et la met à jour en continu. Elle calcule à l'avance la carto de **tout le pays** : chaque société active est rangée dans un groupe. Le registre donne une mère à chaque société qui en a une (l'arbre). Les listes de sociétés consolidées publiées par les groupes rattachent à leur groupe les sociétés que le registre ne relie pas. Le consultant donne le nom d'une société et lit sa carto : cette société, ses filiales et leurs sous-filiales, jamais les autres filiales de ses actionnaires. Elle est déjà calculée, datée de 7 jours au plus. Chaque lien y porte sa preuve, une confiance A/B/C et l'indication « ciblable » ou non. Aucun humain n'a à écrire de réglages pour qu'une carto existe. Mesure du 2026-10-16, sans aucun réglage : 83 % de LVMH et 83 % de VINCI.

## Utilisateurs

### Persona principal : le consultant Youno
- **Rôle** : prépare et mène des missions commerciales pour des clients B2B. Il livre au client la liste des sociétés d'un groupe cible.
- **Ce qui le gêne** :
  - les cartos actuelles sont incomplètes, et il ne sait pas ce qui manque ;
  - il ne peut pas justifier un lien devant le client : il n'a pas de preuve ;
  - refaire une carto à la main prend des heures.
- **Ce qui le motive** : livrer vite une carto complète et défendable.
- **Ce qui le ferait arrêter** : une seule fausse filiale livrée au client, ou des données visiblement périmées.

### Persona secondaire : le responsable de la base (Loïc)
- **Rôle** : fait tourner la mise à jour du registre, cherche et dépose les documents de périmètre des groupes, règle le moteur.
- **Ce qui le gêne** : le stock local date du 2026-03-04. Rien ne signale une mise à jour ratée.
- **Ce qui le motive** : une base et des cartos fraîches sans intervention manuelle, et des échecs visibles tout de suite.

## Parcours utilisateurs

### US1 — La base se met à jour toute seule (Priorité : P1) 🎯 MVP
**En tant que** responsable de la base, **je veux** que les sociétés et les liens se mettent à jour automatiquement depuis l'INPI et l'INSEE, **pour que** toute carto reflète l'état actuel du registre.

**Pourquoi P1** : sans elle, chaque carto rend des données de mars 2026, soit sept mois de retard.
**Testable seule** : on applique une mise à jour sur la base, puis on vérifie qu'une société créée, un lien nouveau et un lien disparu sont bien pris en compte, sans lancer de carto.

**Scénarios d'acceptation**
1. **Étant donné** une base à jour au jour J, **quand** l'INPI publie un nouveau lien au jour J+1, **alors** ce lien est dans la base en 7 jours au plus, avec sa date de début.
2. **Étant donné** un lien actif dans la base, **quand** il disparaît du registre, **alors** il est fermé (date de fin renseignée), jamais supprimé.
3. **Étant donné** une mise à jour qui échoue (source injoignable, fichier invalide), **quand** le responsable ouvre l'app, **alors** il voit l'échec, sa date et sa cause, et la base reste dans son dernier état valide.

### US7 — La carto du pays se calcule seule (Priorité : P1) 🎯 MVP
*Ajoutée le 2026-10-16, décision de Loïc : la carto du pays devient le parcours principal, et tout le pays est cartographié avant la mise en ligne.*

**En tant que** responsable de la base, **je veux** que chaque société active de France soit rangée dans la carto de son groupe, recalculée seule, **pour qu'**un consultant n'ait qu'à lire une carto déjà faite.

**Pourquoi P1** : c'est ce qui rend une carto complète sans travail humain. Sans elle, chaque groupe demande des réglages écrits à la main, et le moteur ne retrouve que 1 à 16 % d'un groupe sans eux (mesure du 2026-10-14).
**Testable seule** : sur le registre du 2026-03-04 et les documents de LVMH et VINCI, on calcule la carto du pays sans interface, puis on compare les cartos de LVMH et VINCI à leurs références avec la non-régression, et on compte les sociétés actives rangées.

**Scénarios d'acceptation**
1. **Étant donné** le registre, **quand** la carto du pays est calculée, **alors** chaque société active a au plus une mère : celle que lui donne le document d'un groupe, sinon celle de l'arbre du registre. La carto d'une société est cette société et tout ce qui descend d'elle ; on ne remonte jamais à sa mère ou à ses actionnaires pour prendre leurs autres filiales. *Précisé le 2026-10-18, décision de Loïc : avant, la carto d'une société était l'arbre entier de son sommet, sœurs comprises.*
2. **Étant donné** le document de périmètre d'un groupe, déposé par le responsable, **quand** la carto du pays est calculée, **alors** chaque société inscrite en intégration globale est rattachée à ce groupe, avec ses propres filiales ; les autres filiales de sa mère au registre n'entrent pas. Chaque société inscrite porte sa preuve (document, ligne, méthode, taux) ; une société mise en équivalence n'entre pas comme filiale (règles de T043).
3. **Étant donné** un groupe mutualiste (Crédit Mutuel), **quand** la carto du pays est calculée, **alors** il reçoit son traitement à part : ses fédérations ne sont pas mêlées dans une même carto, comme le fait la règle de l'arbre.
4. **Étant donné** une base mise à jour, **quand** 7 jours sont passés, **alors** chaque carto a été recalculée sur la base à jour, et elle affiche la date des données utilisées.
5. **Étant donné** un document déposé, **quand** il est lu, **alors** le responsable voit combien de lignes ont été retrouvées dans le registre, et les lignes refusées avec leur raison (homonymes, introuvables).

### US2 — Lire la carto d'un groupe (Priorité : P1) 🎯 MVP
*Réécrite le 2026-10-16 : le consultant lit une carto déjà calculée (US7) ; il n'écrit plus de réglages avant d'avoir une carto.*

**En tant que** consultant, **je veux** chercher un groupe et lire son arbre en France avec les preuves, **pour** livrer au client une carto complète et défendable.

**Pourquoi P1** : c'est le service rendu. Sans lui, l'app n'a pas d'usage.
**Testable seule** : sur une carto du pays déjà calculée (stock de mars 2026), on cherche LVMH, on exporte le CSV et on le compare à la référence.

**Scénarios d'acceptation**
1. **Étant donné** un consultant connecté, **quand** il saisit « LVMH », une filiale ou un SIREN, **alors** l'app lui montre la carto de cette société : elle en tête, avec son SIREN, puis ses filiales et sous-filiales. Les autres filiales de sa mère ou de ses actionnaires n'y sont pas. Si elle a une mère, l'app la nomme au-dessus de l'arbre, avec son SIREN et un lien qui ouvre la carto de la mère ; ses autres filiales ne s'affichent pas (décidé le 2026-10-18). Une mère entrepreneur individuel est dite « personne physique, non affichée », sans lien.
2. **Étant donné** un groupe trouvé, **quand** il l'ouvre, **alors** il voit un arbre dépliable, sans attendre de calcul. Chaque société porte son SIREN, son niveau et sa maison mère directe. Chaque lien porte sa preuve en clair, sa confiance A/B/C, l'indication ciblable Oui ou Non avec la raison, et le marquage d'opposition à la prospection.
3. **Étant donné** un arbre affiché, **quand** il le regarde, **alors** il voit la date des données et si la carto a été corrigée à la main ou calculée seule.
4. **Étant donné** un arbre affiché, **quand** il exporte, **alors** il obtient un CSV. Ce fichier ne contient aucun nom de dirigeant personne physique et indique la date des données utilisées.

### US8 — Corriger la carto d'un groupe (Priorité : P2)
*Ajoutée le 2026-10-16 : les réglages écrits à la main (marques, exclusions, organigramme) deviennent des corrections facultatives.*

**En tant que** consultant, **je veux** ajouter des marques ou des exclusions à un groupe, **pour** corriger une carto que les règles seules ont mal faite.

**Pourquoi P2** : la carto existe sans correction. La correction améliore un groupe ; elle ne bloque pas la livraison.
**Testable seule** : sur LVMH, on ajoute les réglages de `config/lvmh.json` comme corrections, puis on compare la carto à la référence : au moins le score des réglages seuls (155/172), mesuré le 2026-10-16 à 166/172 avec le document.

**Scénarios d'acceptation**
1. **Étant donné** la carto d'un groupe, **quand** il enregistre une correction, **alors** elle est versionnée avec son auteur et sa date, l'ancienne version est conservée, et la carto du groupe est recalculée avec elle.
2. **Étant donné** une correction, **quand** la carto est recalculée, **alors** il voit combien de sociétés elle a ajoutées et retirées. Une marque fausse peut ajouter 150 sociétés (Equans dans VINCI) : l'effet se voit avant la livraison.
3. **Étant donné** deux consultants qui corrigent le même groupe, **quand** le second enregistre, **alors** sa version est refusée tant qu'elle ne part pas de la dernière.

### US3 — L'IA propose des corrections (Priorité : P3)
*Rétrogradée en P3 le 2026-10-16 : la carto ne dépend plus des réglages, et les documents de périmètre sont cherchés par Loïc lui-même, avec son forfait Claude Code (aucune recherche par OpenRouter).*

**En tant que** consultant, **je veux** que l'app propose des marques et des holdings à exclure, chacune avec sa source, **pour** corriger un groupe sans partir d'une page blanche.

**Testable seule** : sur LVMH, VINCI et CMAF, on compare les propositions aux réglages validés de `config/`.

**Scénarios d'acceptation**
1. **Étant donné** un groupe, **quand** le consultant demande une proposition, **alors** il reçoit des corrections pré-remplies, chacune avec sa source. Rien n'est appliqué tant qu'il ne l'a pas enregistrée comme correction.
2. **Étant donné** une proposition, **quand** une marque est ambiguë (homonymes au registre), **alors** elle est rangée en « ambiguë » : elle exigera une deuxième preuve.

### US4 — Traiter les cas douteux (Priorité : P2)
**En tant que** consultant, **je veux** une liste des cas douteux (confiance C, co-entreprises, participations, sociétés étrangères, sociétés mises en équivalence), chacun avec ses indices pour et contre, **pour** décider vite ce que je livre.

**Pourquoi P2** : l'arbre marque déjà ces cas en confiance C. La liste rend seulement leur traitement plus rapide.
**Testable seule** : sur VINCI, on vérifie que les sociétés « en plus » qui sont des cas douteux apparaissent dans la liste, avec leurs indices. *Décidé le 2026-10-08, T027* : les sociétés « en plus » retenues en confiance A ou B, sans mandat extérieur, ne sont pas des cas : le moteur n'a pas de raison de douter d'elles.

**Scénarios d'acceptation**
1. **Étant donné** une carto, **quand** il ouvre la liste, **alors** chaque cas montre ses indices et la règle qui l'a placé là.
2. **Étant donné** un cas, **quand** il le retient ou l'écarte, **alors** sa décision est enregistrée avec son nom et sa date, et elle est reprise au calcul suivant du groupe.

### US5 — Export HubSpot et Cargo (Priorité : P3)
**En tant que** consultant, **je veux** exporter la carto au format d'import HubSpot et Cargo (les 6 tables du skill account-mapping), **pour** charger le résultat chez le client sans retraitement.

**Testable seule** : on lance la validation du skill sur l'export des trois groupes de référence, et on attend 0 erreur.

### US6 — Site web et page LinkedIn — *retirée*
*Retirée le 2026-10-13, décision de Loïc : cartoFR ne fait pas d'enrichissement, seulement la carto des entreprises françaises. Voir « Hors périmètre ».*

### Cas limites
- **Société introuvable** : message « Aucune société trouvée », avec la possibilité de saisir directement un SIREN.
- **Société seule, sans aucun lien au registre** : elle est son propre groupe ; la carto la montre seule, avec un avertissement qui explique pourquoi.
- **Sommet d'arbre qui est une personne** (entrepreneur individuel qui préside des sociétés) : la carto n'affiche ni son nom ni son SIREN. Le groupe est présenté par sa plus grande société, et la tête est dite « personne physique, non affichée » (garde-fou 6).
- **Document de périmètre ancien ou d'un autre groupe** : les lignes retrouvées et refusées sont montrées au dépôt (US7, scénario 5) ; un document se remplace, l'ancien est conservé.
- **Site d'un groupe qui refuse le téléchargement** (BFCM, 403) : le document est déposé à la main, en PDF.
- **Mise à jour en cours pendant un calcul** : le calcul utilise une photo cohérente de la base et affiche sa date.
- **Société avec `diffusionCommerciale = false`** : affichée et exportée, marquée « opposition à la prospection », jamais cachée.
- **Société non diffusible à l'INSEE** : affichée et exportée, marquée « non diffusible » (décidé le 2026-10-06).
- **Groupe à caisses locales sans mandat** (Crédit Mutuel) : traitement à part (US7, scénario 3) ; ce qui reste hors d'atteinte est annoncé dans le résultat, pas masqué.

## Exigences

### Exigences fonctionnelles
- **FR-001** : la base DOIT intégrer les changements du registre RNE (INPI) et de SIRENE (INSEE) automatiquement, 7 jours au plus après leur publication. — *US1*
- **FR-002** : chaque société et chaque lien DOIVENT porter une date de début et une date de fin. Un lien disparu est fermé, jamais supprimé. — *US1*
- **FR-003** : chaque mise à jour DOIT être tracée (date, source, volumes, succès ou échec). Un échec DOIT être visible dans l'app, et la base DOIT rester dans son dernier état valide. — *US1*
- **FR-012** : le système DOIT donner à chaque société active au plus une mère, à partir du registre seul (arbre à une mère, T045) et des documents de périmètre déposés, et la carto d'une société DOIT être cette société et tout ce qui descend d'elle, jamais les autres filiales de ses actionnaires, sans validation humaine et sans appel extérieur. Chaque carto DOIT avoir 7 jours de retard au plus sur la base. — *US7*
- **FR-013** : le système DOIT accepter un document de périmètre par groupe (PDF ou page déposés), le garder, et rendre les lignes retrouvées et refusées avec leur raison. — *US7*
- **FR-014** : le système DOIT traiter les groupes mutualistes à part, sans mêler leurs fédérations. — *US7*
- **FR-004** : l'app DOIT trouver le groupe d'une société par son nom ou son SIREN. — *US2*
- **FR-006** : le moteur DOIT calculer chaque carto à partir de la base seule, sans appel extérieur, avec des règles écrites. Chaque lien retenu DOIT porter sa preuve, sa confiance A/B/C, et l'indication ciblable avec sa raison. — *US2, US7*
- **FR-007** : l'app DOIT afficher l'arbre et l'exporter en CSV. Le résultat DOIT indiquer la date des données et si la carto a été corrigée, marquer l'opposition à la prospection et la non-diffusion INSEE, et ne contenir aucun nom de dirigeant personne physique. — *US2*
- **FR-005** : l'app DOIT permettre de saisir et de versionner des corrections d'un groupe (marques, exclusions, organigramme), avec auteur et date. Une correction s'applique au calcul suivant du groupe, et son effet (sociétés ajoutées, retirées) DOIT être affiché. — *US8* (*réécrite le 2026-10-16 : plus d'étape de validation*)
- **FR-008** : l'app DOIT pouvoir proposer des corrections pré-remplies et sourcées, sans effet tant qu'elles ne sont pas enregistrées. — *US3*
- **FR-009** : l'app DOIT lister les cas douteux avec leurs indices, et enregistrer la décision du consultant pour les calculs suivants. — *US4*
- **FR-010** : l'app DOIT exporter les 6 tables du skill account-mapping. — *US5*
- ~~**FR-011** : enrichissement par le domaine et la page LinkedIn.~~ — *retirée le 2026-10-13*

### Entités principales
- **Société** : SIREN, nom, siège, activité, effectif, statut, opposition à la prospection, dates de début et de fin.
- **Lien** : société dirigeante → société dirigée, rôle (président, gérant, associé…), source, dates de début et de fin.
- **Dirigeant personne** : usage interne au calcul seulement (preuve de dirigeants communs). Jamais affiché ni exporté.
- **Arbre** : pour chaque société, sa mère dans le registre et son sommet (T045). Dérivé des liens, sans nom.
- **Document de périmètre** : groupe, fichier, date de dépôt, lignes retrouvées et refusées.
- **Mise à jour** : date, source, volumes ajoutés et fermés, statut.
- **Groupe** : tête (SIREN), document de périmètre éventuel, versions de corrections (auteur, date).
- **Carto** : groupe, date des données, corrigée ou non, sociétés et liens retenus, avec preuve et confiance. Une carto du pays, commune à toutes les organisations ; les corrections et décisions appartiennent à une organisation.
- **Organisation et utilisateur** : le compte Youno et ses consultants.

## Critères de succès

- **SC-001 — Justesse, sans correction** : sur la carto obtenue sans aucune correction (registre et document seuls), retrouvées ≥ 90 % pour LVMH (réf. Basile, 172), ≥ 81 % pour VINCI (réf. Basile, 1 007), ≥ 83 % pour CMAF (réf. Cargo, 52). Les « en plus » que le document du groupe n'inscrit pas ne dépassent pas 16 pour LVMH ni 193 pour VINCI. Mesure : la non-régression, tête seule et document (`--perimetre --sans-reglages`), sur une photo figée de la base. Référence au 2026-10-16 : LVMH 83 % · 7 en plus non inscrits, VINCI 83 % · 107, CMAF 2 % (pas de document, pas de traitement mutualiste). *Réécrit le 2026-10-16 : les cibles du prototype ne baissent pas, elles se mesurent sans réglage humain (décision de Loïc du 2026-10-14).*
- **SC-002 — Lecture** : moins de 10 secondes entre la recherche d'une société et l'affichage de l'arbre de son groupe, pour un groupe de la taille de VINCI. Mesure : durée journalisée de chaque ouverture. *Réécrit le 2026-10-16 : le chronométrage d'une saisie de réglages est sans objet.*
- **SC-003 — Fraîcheur de la base** : 100 % des changements tirés au hasard (10 par semaine, dans les publications INPI et INSEE) sont dans la base en 7 jours au plus. Mesure : contrôle hebdomadaire. Référence : 216 jours de retard au 2026-10-06.
- **SC-004 — Vitesse du moteur** : la carto d'un groupe de la taille de VINCI est calculée en moins de 5 minutes. Mesure : durée journalisée. Référence au 2026-10-16 : 75 s sans correction, 165 à 180 s avec.
- **SC-005 — Licence INPI** : 0 nom de dirigeant personne physique issu du registre dans les écrans et les exports, ni le SIREN d'un entrepreneur individuel. Les raisons sociales SIRENE, même quand elles contiennent un nom de personne, sont des noms de société et restent affichées (précisé le 2026-10-07). Mesure : un test automatique compare chaque texte produit à la table des dirigeants, sur les trois groupes de référence.
- **SC-006 — Adoption** : 3 mois après la mise en ligne, 100 % des cartos de groupe livrées en mission Youno sortent de l'app. Mesure : liste des missions comparée aux cartos exportées. Référence : 0 % aujourd'hui.
- ~~**SC-007 — IA**~~ : *retiré le 2026-10-16. Il comptait les corrections d'une proposition de réglages ; la carto se juge désormais sans correction (SC-001).*
- **SC-008 — Couverture du pays, avant la mise en ligne** : 100 % des sociétés actives rangées dans une carto, et un document de périmètre pour 100 % des groupes cotés à Paris qui publient leur liste de sociétés consolidées. Mesure : comptage dans la base, et liste des sociétés cotées d'Euronext Paris comparée aux documents déposés. Référence au 2026-10-16 : 0 carto du pays, 4 documents (VINCI, LVMH, Fnac Darty, Edenred).
- **SC-009 — Fraîcheur des cartos** : 100 % des cartos ont 7 jours de retard au plus sur la base. Mesure : contrôle hebdomadaire de la date des données de chaque carto.

## Hors périmètre (V1)

- **Alertes** (nouvelle filiale, changement de dirigeant) : la base historisée les rendra possibles plus tard.
- **Poussée directe dans le CRM** : un export de fichiers suffit en V1 (US5).
- **Filiales à l'étranger** (LEI, rapports annuels) : les registres français ne les voient pas. C'est un autre chantier.
- **Pourcentages de détention** : le registre dit qui dirige, pas qui possède combien. Seul le taux d'intérêt écrit dans un document de périmètre est repris, comme preuve.
- **Décideurs et contacts** : contraintes légales lourdes (licence INPI, RGPD).
- **Accès client** : seule l'équipe Youno se connecte en V1.
- **Enrichissement** (site web, page LinkedIn, toute donnée de prospection) : décidé le 2026-10-13 (Loïc), US6 retirée.
- **Recherche automatique des documents de périmètre** : Loïc les cherche lui-même (décidé le 2026-10-16). L'app les reçoit, elle ne va pas les chercher.
- *Retiré de cette liste le 2026-10-16* : la « carto en masse » est devenue la carto du pays (US7).

## Hypothèses

- Le stock RNE par FTP et les mises à jour de l'INPI restent accessibles avec le compte actuel.
- Les mises à jour SIRENE suffisent pour tenir 7 jours de retard au plus.
- Les règles du moteur et de l'arbre, calées sur LVMH, VINCI et CMAF, gardent leur justesse sur des groupes d'autres formes. Le pilote Fnac Darty et Edenred (2026-10-15) n'a pas de référence pour le vérifier.
- Un groupe coté publie une liste de ses sociétés consolidées que l'extraction sait lire. Le 2026-10-15, l'extraction de T042 ne lisait aucune ligne des documents de Fnac Darty et d'Edenred : chaque nouveau format de liste demande du travail.
- Trouver les documents de quelques centaines de groupes tient dans le temps de Loïc avant la mise en ligne (5 à 15 minutes par groupe mesurées à la main, moins avec Claude Code). À mesurer sur les 20 premiers.
- Un usage interne par Youno, sans redistribution aux clients d'autre chose que la carto livrée, est compatible avec la licence INPI. À confirmer.

## Questions ouvertes

- **Traitement des groupes mutualistes** : quelle règle sépare les fédérations du Crédit Mutuel (document par fédération, caisse fédérale comme tête, autre) ? À mesurer sur CMAF avant d'écrire la tâche.
- ~~**Taille des cartos du pays dans la base de l'app**~~ : tranché le 2026-10-16 dans `ARCHI.md` (ADR-006) : la carto du pays reste sur le worker, dans `pays.duckdb` ; Postgres ne garde que les cartos corrigées.

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G1-G4 Git, branches, PR, squash | ➖ | Document seul |
| G5 Aucun secret dans le code | ➖ | Document seul |
| G6 Licence INPI : aucun nom de personne, opposition marquée | ⚠️ | FR-007 et SC-005. **Condition nouvelle** : le sommet d'un arbre peut être un entrepreneur individuel. Ni son nom ni son SIREN ne s'affichent (cas limites, SC-005) |
| R1 Français | ✅ | Interface interne Youno, entièrement en français |
| R2 Responsive, mobile-first | ⚠️ | L'arbre et l'écran de correction fonctionnent dès 320 px : à porter dans les tâches de US2 et US8 |
| R3 Accessibilité | ⚠️ | L'arbre se parcourt au clavier, la confiance ne passe pas par la seule couleur, et « corrigée / calculée seule » non plus |
| R4 RGPD | ⚠️ | Inchangé : dirigeants en usage interne, registre des traitements (T031). L'arbre ne lit que les liens entre sociétés |
| R5 Hébergement UE | ✅ | Les documents déposés restent sur le serveur, en Allemagne. Aucune IA dans le calcul des cartos ; la recherche des documents se fait hors de l'app |
| R6 Aucune donnée client réelle en dev | ✅ | Registre et documents publiés par les groupes : données publiques. Les références Basile restent hors git |
| R7 Isolation multi-tenant | ⚠️ | **Condition nouvelle** : la carto du pays est commune à toutes les organisations (données publiques dérivées du registre). Corrections, décisions et exports appartiennent à une organisation, cloisonnée en RLS, avec un test « A ne voit pas les corrections de B ». À porter dans l'architecture |
| R8 Tests sur la logique métier | ⚠️ | Recollage des arbres, traitement mutualiste et rangement de chaque société arrivent avec leurs tests ; SC-001 sert de non-régression |
| P1 L'IA ne décide pas qu'une société est une filiale | ✅ | Aucune IA dans le calcul (FR-012) ; US3 ne fait que proposer des corrections |
| P2 Les réglages d'un groupe sont validés par un humain | ⚠️ | **Amendé le 2026-10-16** (décision de Loïc) : une carto existe sans validation humaine ; une correction est versionnée, datée et son effet affiché (FR-005). Texte et raison dans `CLAUDE.md` |
| P3 Aucun appel extérieur pendant une carto | ✅ | FR-006, FR-012 : les documents sont déposés, jamais téléchargés pendant un calcul |
| P4 Un lien n'est jamais effacé, il est fermé | ✅ | FR-002. L'arbre est dérivé des liens et recalculé, jamais une source |
| P5 Pas de régression silencieuse | ✅ | SC-001, mesuré sans correction sur LVMH, VINCI et CMAF |
| P6 Le registre ne quitte pas le worker | ⚠️ | La carto du pays met dans la base de l'app des sociétés et des liens retenus, jamais une personne. Le volume (question ouverte) se tranche dans l'architecture |
| P7 La logique métier vit dans le paquet Python | ✅ | Arbre, recollage et moteur dans `worker/` |

Aucun ⛔.

## Calendrier

- **Équipe** : Loïc seul, avec Claude Code, à temps partiel.
- **MVP (US1, US7 et US2)** : US1 et l'arbre (T045) sont faits. Le recollage des arbres, le traitement mutualiste et la lecture d'une carto précalculée sont à découper en tâches.
- **Documents de périmètre** : en parallèle, par Loïc. Mesurer le temps sur les 20 premiers groupes, puis fixer la date de la couverture complète.
- **Mise en ligne** : quand SC-008 est tenu, pas avant.
- **P2 (US8 et US4)** : après le MVP.
- **Point d'adoption (SC-006)** : 3 mois après la mise en ligne.
- **Relecture juridique** (licence INPI, RGPD) : avant toute commercialisation, pas avant l'usage interne Youno.
