# PRD — cartoFR

Date : 2026-10-06. Sources : `rapportSaaS.md` (vision), `rapport.md` (résultats du prototype).

## Vision produit

**Le problème**
Pour une mission, un consultant Youno doit connaître toutes les sociétés françaises d'un groupe client : la maison mère, les filiales et les sous-filiales. La carto Cargo actuelle cherche sur le web, société par société, et n'en trouve qu'une sur 4 à une sur 9 (19 sociétés pour LVMH, contre 172 chez Basile). Basile fait mieux, mais à la main, sans donner les liens entre sociétés et sans la preuve de chaque lien.

**La solution**
L'app tient sa propre copie du registre français (SIRENE et RNE), avec tous les liens « société A dirige société B », et la met à jour en continu. Le consultant donne le nom du groupe, valide les réglages, puis obtient en quelques minutes l'arbre du groupe. Chaque lien y porte sa preuve, une confiance A/B/C et l'indication « ciblable » ou non. Le prototype retrouve ainsi 90 % de LVMH, 81 % de VINCI et 83 % de CMAF.

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
- **Rôle** : fait tourner la mise à jour du registre et règle le moteur.
- **Ce qui le gêne** : le stock local date du 2026-03-04. Rien ne signale une mise à jour ratée.
- **Ce qui le motive** : une base fraîche sans intervention manuelle, et des échecs visibles tout de suite.

## Parcours utilisateurs

### US1 — La base se met à jour toute seule (Priorité : P1) 🎯 MVP
**En tant que** responsable de la base, **je veux** que les sociétés et les liens se mettent à jour automatiquement depuis l'INPI et l'INSEE, **pour que** toute carto ouverte reflète l'état actuel du registre.

**Pourquoi P1** : sans elle, chaque carto rend des données de mars 2026, soit sept mois de retard.
**Testable seule** : on applique une mise à jour sur la base, puis on vérifie qu'une société créée, un lien nouveau et un lien disparu sont bien pris en compte, sans lancer de carto.

**Scénarios d'acceptation**
1. **Étant donné** une base à jour au jour J, **quand** l'INPI publie un nouveau lien au jour J+1, **alors** ce lien est dans la base en 7 jours au plus, avec sa date de début.
2. **Étant donné** un lien actif dans la base, **quand** il disparaît du registre, **alors** il est fermé (date de fin renseignée), jamais supprimé.
3. **Étant donné** une mise à jour qui échoue (source injoignable, fichier invalide), **quand** le responsable ouvre l'app, **alors** il voit l'échec, sa date et sa cause, et la base reste dans son dernier état valide.

### US2 — Cartographier un groupe (Priorité : P1) 🎯 MVP
**En tant que** consultant, **je veux** saisir un groupe, valider ses réglages puis obtenir son arbre en France avec les preuves, **pour** livrer au client une carto complète et défendable.

**Pourquoi P1** : c'est le service rendu. Sans lui, l'app n'a pas d'usage.
**Testable seule** : sur la base existante (stock de mars 2026), on cartographie LVMH, on exporte le CSV et on le compare à la référence avec `compare.py`.

**Scénarios d'acceptation**
1. **Étant donné** un consultant connecté, **quand** il saisit « LVMH » ou un SIREN, **alors** l'app propose les sociétés têtes possibles, avec leur SIREN, et il en choisit une.
2. **Étant donné** une tête choisie, **quand** il saisit les marques (sûres ou ambiguës), les exclusions et l'organigramme, puis valide, **alors** les réglages sont enregistrés avec leur auteur et leur date, et le moteur peut tourner.
3. **Étant donné** des réglages validés, **quand** le moteur a fini, **alors** il voit un arbre dépliable. Chaque société porte son SIREN, son niveau et sa maison mère directe. Chaque lien porte sa preuve en clair, sa confiance A/B/C, l'indication ciblable Oui ou Non avec la raison, et le marquage d'opposition à la prospection.
4. **Étant donné** un arbre affiché, **quand** il exporte, **alors** il obtient un CSV. Ce fichier ne contient aucun nom de dirigeant personne physique et indique la date des données utilisées.
5. **Étant donné** des réglages existants pour un groupe, **quand** il les modifie, **alors** la nouvelle version doit être validée avant d'être utilisée, et l'ancienne est conservée.

### US3 — L'IA propose les réglages (Priorité : P2)
**En tant que** consultant, **je veux** que l'app propose les marques, les maisons (avec leur nom légal) et les holdings à exclure, **pour** ne plus écrire les réglages à partir d'une page blanche.

**Pourquoi P2** : c'est un gros gain de temps sur un nouveau groupe, mais un humain peut écrire les réglages seul.
**Testable seule** : sur LVMH, VINCI et CMAF, on compare les propositions aux réglages validés de `config/` et on compte les corrections.

**Scénarios d'acceptation**
1. **Étant donné** une tête choisie, **quand** le consultant demande une proposition, **alors** il reçoit des réglages pré-remplis, chacun avec sa source. Rien n'est utilisé avant sa validation.
2. **Étant donné** une proposition, **quand** une marque est ambiguë (homonymes au registre), **alors** elle est rangée en « ambiguë » : elle exigera une deuxième preuve.

### US4 — Traiter les cas douteux (Priorité : P2)
**En tant que** consultant, **je veux** une liste des cas douteux (confiance C, co-entreprises, participations, sociétés étrangères), chacun avec ses indices pour et contre, **pour** décider vite ce que je livre.

**Pourquoi P2** : l'arbre marque déjà ces cas en confiance C. La liste rend seulement leur traitement plus rapide.
**Testable seule** : sur VINCI, on vérifie que les sociétés « en plus » qui sont des cas douteux (confiance C, co-entreprise, participation sans contrôle, société étrangère) apparaissent dans la liste, avec leurs indices. *Décidé le 2026-10-08, T027* : les sociétés « en plus » retenues en confiance A ou B, sans mandat extérieur, ne sont pas des cas : le moteur n'a pas de raison de douter d'elles, et les lister reviendrait à classer « douteuse » toute confiance B. Mesure du 2026-10-08 : 93 des 176 sociétés « en plus » de VINCI sont dans la liste ; les 83 autres sont en confiance B (75) ou A (8).

**Scénarios d'acceptation**
1. **Étant donné** une carto finie, **quand** il ouvre la liste, **alors** chaque cas montre ses indices et la règle qui l'a placé là.
2. **Étant donné** un cas, **quand** il le retient ou l'écarte, **alors** sa décision est enregistrée avec son nom et sa date, et elle est reprise lors de la carto suivante du même groupe.

### US5 — Export HubSpot et Cargo (Priorité : P3)
**En tant que** consultant, **je veux** exporter la carto au format d'import HubSpot et Cargo (les 6 tables du skill account-mapping), **pour** charger le résultat chez le client sans retraitement.

**Testable seule** : on lance la validation du skill sur l'export des trois groupes de référence, et on attend 0 erreur.

### US6 — Site web et page LinkedIn (Priorité : P3)
**En tant que** consultant, **je veux** voir le domaine et la page LinkedIn de chaque société, **pour** préparer la prospection.

**Testable seule** : sur LVMH, on compte la part des sociétés ciblables qui ont un domaine renseigné.
Ces données s'ajoutent à la base lors de sa mise à jour, jamais pendant le calcul d'une carto.

### Cas limites
- **Groupe introuvable** : message « Aucune société trouvée », avec la possibilité de saisir directement le SIREN de la tête.
- **Tête sans aucun lien au registre** : l'arbre est rendu réduit à la tête, avec un avertissement qui explique pourquoi.
- **Tête radiée ou fermée** : elle est signalée avant le lancement, et le consultant confirme.
- **Mise à jour en cours pendant une carto** : la carto utilise une photo cohérente de la base et affiche sa date.
- **Deux consultants modifient les réglages d'un même groupe** : la seconde validation est refusée tant qu'elle ne part pas de la dernière version.
- **Société avec `diffusionCommerciale = false`** : elle est affichée et exportée, marquée « opposition à la prospection », jamais cachée.
- **Société non diffusible à l'INSEE** : affichée et exportée, marquée « non diffusible », comme l'opposition à la prospection (décidé le 2026-10-06).
- **Groupe à caisses locales sans mandat** (Crédit Mutuel) : la limite est annoncée dans le résultat, pas masquée.

## Exigences

### Exigences fonctionnelles
- **FR-001** : la base DOIT intégrer les changements du registre RNE (INPI) et de SIRENE (INSEE) automatiquement, 7 jours au plus après leur publication. — *US1*
- **FR-002** : chaque société et chaque lien DOIVENT porter une date de début et une date de fin. Un lien disparu est fermé, jamais supprimé. — *US1*
- **FR-003** : chaque mise à jour DOIT être tracée (date, source, volumes, succès ou échec). Un échec DOIT être visible dans l'app, et la base DOIT rester dans son dernier état valide. — *US1*
- **FR-004** : l'app DOIT permettre de choisir la tête d'un groupe par son nom ou son SIREN. — *US2*
- **FR-005** : l'app DOIT permettre de saisir, de versionner et de valider les réglages d'un groupe. Le moteur ne DOIT tourner que sur une version validée. — *US2*
- **FR-006** : le moteur DOIT calculer l'arbre à partir de la base seule, sans appel extérieur, avec les règles écrites du prototype. Chaque lien retenu DOIT porter sa preuve, sa confiance A/B/C, et l'indication ciblable avec sa raison. — *US2*
- **FR-007** : l'app DOIT afficher l'arbre et l'exporter en CSV. Le résultat DOIT indiquer la date des données, marquer l'opposition à la prospection et la non-diffusion INSEE, et ne contenir aucun nom de dirigeant personne physique. — *US2*
- **FR-008** : l'app DOIT proposer des réglages pré-remplis et sourcés, qui restent sans effet tant qu'un humain ne les a pas validés. — *US3*
- **FR-009** : l'app DOIT lister les cas douteux avec leurs indices, et enregistrer la décision du consultant pour les cartos suivantes. — *US4*
- **FR-010** : l'app DOIT exporter les 6 tables du skill account-mapping. — *US5*
- **FR-011** : la mise à jour de la base DOIT pouvoir ajouter le domaine et la page LinkedIn des sociétés. — *US6*

### Entités principales
- **Société** : SIREN, nom, siège, activité, effectif, statut, opposition à la prospection, dates de début et de fin.
- **Lien** : société dirigeante → société dirigée, rôle (président, gérant, associé…), source, dates de début et de fin.
- **Dirigeant personne** : usage interne au calcul seulement (preuve de dirigeants communs). Jamais affiché ni exporté.
- **Mise à jour** : date, source, volumes ajoutés et fermés, statut.
- **Groupe** : tête (SIREN) et versions de réglages (marques sûres ou ambiguës, exclusions, organigramme, auteur, date de validation).
- **Carto** : groupe, version de réglages, date des données, sociétés et liens retenus, avec preuve et confiance.
- **Organisation et utilisateur** : le compte Youno et ses consultants. Chaque carto appartient à une organisation.

## Critères de succès

- **SC-001 — Justesse** : retrouvées ≥ 90 % pour LVMH (réf. Basile, 172), ≥ 81 % pour VINCI (réf. Basile, 1 007), ≥ 83 % pour CMAF (réf. Cargo, 52). Les « en plus » ne dépassent pas 16 pour LVMH ni 193 pour VINCI (au plus 10 % au-dessus du prototype). Mesure : `compare.py` sur une photo figée de la base. Référence : les scores du prototype au 2026-10-06.
- **SC-002 — Durée** : moins de 30 minutes entre la saisie d'un groupe de moins de 200 sociétés et l'export CSV, réglages écrits à la main compris. Mesure : trois sessions chronométrées sur trois groupes jamais réglés. Référence : réglages écrits en JSON à la main, temps non mesuré.
- **SC-003 — Fraîcheur** : 100 % des changements tirés au hasard (10 par semaine, dans les publications INPI et INSEE) sont dans la base en 7 jours au plus. Mesure : contrôle hebdomadaire. Référence : 216 jours de retard au 2026-10-06 (stock du 2026-03-04).
- **SC-004 — Vitesse du moteur** : une carto de la taille de VINCI (environ 1 000 sociétés) est calculée en moins de 5 minutes. Mesure : durée journalisée de chaque carto.
- **SC-005 — Licence INPI** : 0 nom de dirigeant personne physique issu du registre des dirigeants dans les écrans et les exports. Les raisons sociales SIRENE, même quand elles contiennent un nom de personne, sont des noms de société et restent affichées (précisé le 2026-10-07). Mesure : un test automatique compare chaque texte produit par le moteur à la table des dirigeants, et vérifie que les noms de société sont ceux de SIRENE, sur les trois groupes de référence.
- **SC-006 — Adoption** : 3 mois après la livraison du MVP, 100 % des cartos de groupe livrées en mission Youno sortent de l'app. Mesure : liste des missions comparée aux cartos exportées. Référence : 0 % aujourd'hui (Basile, Cargo ou à la main).
- **SC-007 — IA (P2)** : après US3, moins de 30 minutes pour tout nouveau groupe, et moins de 5 corrections humaines en moyenne par proposition sur LVMH, VINCI et CMAF.

## Hors périmètre (V1)

- **Alertes** (nouvelle filiale, changement de dirigeant) : la base historisée les rendra possibles plus tard. Le MVP sert d'abord la carto.
- **Poussée directe dans le CRM** : un export de fichiers suffit en V1 (US5).
- **Carto en masse** d'une liste de comptes : un groupe à la fois tant que la qualité n'est pas tenue.
- **Filiales à l'étranger** (LEI, rapports annuels) : les registres français ne les voient pas. C'est un autre chantier.
- **Pourcentages de détention** : le registre dit qui dirige, pas qui possède combien.
- **Décideurs et contacts** : contraintes légales lourdes (licence INPI, RGPD).
- **Accès client** : seule l'équipe Youno se connecte en V1.

## Hypothèses

- Le stock RNE par FTP et les mises à jour de l'INPI (API « diff » ou nouveaux stocks) restent accessibles avec le compte actuel.
- Les mises à jour SIRENE (fichiers mensuels et API des changements) suffisent pour tenir 7 jours de retard au plus.
- Les règles du moteur, calées sur LVMH, VINCI et CMAF, gardent leur justesse sur des groupes d'autres formes.
- Un usage interne par Youno, sans redistribution aux clients d'autre chose que la carto livrée, est compatible avec la licence INPI. À confirmer.

## Questions ouvertes

- Quelle **source de mise à jour INPI** utiliser : l'API diff quotidienne ou les nouveaux stocks FTP ? À trancher dans l'architecture.

## Contrôle constitutionnel

| Règle | Verdict | Sur quoi |
|---|---|---|
| G1-G4 Git, branches, PR, squash | ➖ | Aucun code à ce stade |
| G5 Aucun secret dans le code | ➖ | Aucun code à ce stade |
| G6 Licence INPI : aucun nom de personne, opposition marquée | ⚠️ | Porté par FR-007 et SC-005. L'opposition est marquée, jamais cachée (cas limites) |
| R1 Français | ✅ | Interface interne Youno, entièrement en français, messages compris |
| R2 Responsive, mobile-first | ⚠️ | L'arbre et la validation des réglages doivent fonctionner dès 320 px : arbre dépliable et liste de cartes. À porter dans l'architecture et les tâches de US2 |
| R3 Accessibilité | ⚠️ | L'arbre doit se parcourir au clavier, et la confiance A/B/C ne passe pas par la seule couleur. À porter dans les tâches de US2 |
| R4 RGPD | ⚠️ | La base stocke des dirigeants personnes (usage interne au calcul). Il faut un registre des traitements, une durée de conservation, aucun nom dans les logs. Relecture juridique avant toute commercialisation (décidé le 2026-10-06) |
| R5 Hébergement UE | ⚠️ | Base, worker, logs et sauvegardes en UE, à imposer dans l'architecture. L'IA (US3) ne reçoit que des données de sociétés, jamais un nom de personne |
| R6 Aucune donnée client réelle en dev | ⚠️ | Les références Basile et les cartos livrées restent hors git et hors de l'app. Les jeux de test de l'app sont tirés du registre public |
| R7 Isolation multi-tenant | ⚠️ | Une seule organisation en V1, mais chaque carto et chaque réglage appartient à une organisation, cloisonnée en RLS dès la V0, avec un test A ne voit pas B |
| R8 Tests sur la logique métier | ⚠️ | Chaque règle du moteur (filiale, maison mère, confiance, ciblable) arrive avec ses tests. SC-001 sert de non-régression |
| P1 L'IA ne décide pas qu'une société est une filiale | ✅ | US3 propose des réglages, et FR-008 les rend sans effet avant validation |
| P2 Réglages validés par un humain | ✅ | FR-005 : le moteur ne tourne que sur une version validée |
| P3 Aucun appel extérieur pendant une carto | ✅ | FR-006. US6 enrichit la base lors de sa mise à jour, pas pendant le calcul |
| P4 Un lien n'est jamais effacé, il est fermé | ✅ | FR-002 |
| P5 Pas de régression silencieuse | ✅ | SC-001, mesuré sur LVMH, VINCI et CMAF |

Aucun ⛔.

## Calendrier

- **Équipe** : Loïc seul, avec Claude Code, à temps partiel.
- **MVP (US1 et US2)** : entre le 2026-11-03 et le 2026-11-17, soit 4 à 6 semaines.
- **Premier test réel** : une carto livrée en mission avec l'app, dans les 2 semaines suivant le MVP.
- **P2 (US3 et US4)** : dans les 4 semaines suivant le MVP.
- **Point d'adoption (SC-006)** : 3 mois après le MVP.
- **Relecture juridique** (licence INPI, RGPD) : avant toute commercialisation, pas avant l'usage interne Youno.
