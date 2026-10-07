-- Réglages de départ : les réglages historiques du prototype (config/*.json),
-- chargés comme version 1 validée de chaque groupe de l'organisation
-- Youno (T018, C4 ; principe 2).
--
-- FICHIER GÉNÉRÉ par worker/scripts/generer_seed_reglages.py : ne pas le
-- modifier à la main, modifier config/*.json puis relancer le script.
--
-- Ces versions ont été validées par un humain du temps du prototype, hors de
-- l'app : origine 'depart', valide_le posé, valide_par nul (voir le
-- commentaire de public.reglages dans 0002_cartos.sql).
--
-- Idempotent : rejouer ce fichier ne change rien. Il crée l'organisation
-- Youno si aucune n'existe, et sinon prend la plus ancienne de ce nom.
-- À jouer après les migrations, en une transaction : psql -v ON_ERROR_STOP=1 -1 -f

insert into public.organisations (nom)
select 'Youno'
where not exists (select 1 from public.organisations where nom = 'Youno');

-- cmaf : config/cmaf.json
with org as (
  select id from public.organisations where nom = 'Youno' order by cree_le, id limit 1
)
insert into public.groupes (organisation_id, tete_siren, nom)
select org.id, '588505354', 'CMAF' from org
on conflict (organisation_id, tete_siren) do nothing;

with g as (
  select g.id, g.organisation_id
  from public.groupes g
  where g.tete_siren = '588505354'
    and g.organisation_id = (
      select id from public.organisations where nom = 'Youno' order by cree_le, id limit 1
    )
)
insert into public.reglages (groupe_id, organisation_id, version, contenu, origine, valide_le)
select g.id, g.organisation_id, 1, $r0${
  "groupe": "CMAF",
  "tete": "588505354",
  "marques_sures": [
    "Credit Mutuel Alliance Federale",
    "Caisse Federale de Credit Mutuel",
    "Banque Federative du Credit Mutuel",
    "BFCM",
    "Credit Industriel et Commercial",
    "CIC",
    "Banque CIC",
    "CM-CIC",
    "Cofidis",
    "Monabanq",
    "Creatis",
    "Targo",
    "Euro-Information",
    "Euro Information",
    "Assurances du Credit Mutuel",
    "ACM",
    "ACM Vie",
    "ACM IARD",
    "GACM",
    "Groupe des Assurances du Credit Mutuel",
    "Serenis Assurances",
    "Lyonnaise de Banque",
    "Banque Transatlantique",
    "Banque Europeenne du Credit Mutuel",
    "Factofrance",
    "LYF",
    "EBRA",
    "Sofinaction",
    "Credit Mutuel Leasing",
    "Credit Mutuel Asset Management",
    "Credit Mutuel Gestion",
    "Credit Mutuel Innovation",
    "Credit Mutuel Impact",
    "Credit Mutuel Home Loan",
    "Credit Mutuel Caution Habitat",
    "Mutuelles Investissement"
  ],
  "marques_ambigues": [
    "Credit Mutuel",
    "Caisse de Credit Mutuel",
    "Caisse Regionale du Credit Mutuel",
    "Federation du Credit Mutuel",
    "Societe du Journal L Est Republicain",
    "L Est Republicain",
    "Le Progres",
    "Dernieres Nouvelles d Alsace",
    "Le Dauphine Libere",
    "Vosges Matin",
    "Le Bien Public",
    "Le Journal de Saone et Loire",
    "Le Republicain Lorrain",
    "La Francaise",
    "New Alpha",
    "Synergie",
    "Satellite"
  ],
  "exclus": [
    "775577018"
  ],
  "exclus_noms": [
    "CREDIT MUTUEL ARKEA",
    "ARKEA"
  ],
  "familles_exclues": [],
  "marques_sures_homonymes": [
    "CIC",
    "ACM",
    "LYF",
    "EBRA",
    "GACM",
    "BFCM",
    "TARGO",
    "CM CIC"
  ],
  "marques_sigles": [],
  "priorite": [
    "355801929",
    "542016381"
  ],
  "organigramme": [
    "Caisse Federale de Credit Mutuel",
    "Banque Federative du Credit Mutuel",
    "Credit Industriel et Commercial",
    "Groupe des Assurances du Credit Mutuel",
    "Cofidis",
    "Euro Information Europeenne de Traitement de l Information",
    "Banque Europeenne du Credit Mutuel",
    "Monabanq",
    "Banque Transatlantique",
    "Lyonnaise de Banque",
    "Factofrance",
    "EBRA",
    "Societe du Journal L Est Republicain"
  ]
}$r0$::jsonb, 'depart', now() from g
on conflict (groupe_id, version) do nothing;

-- lvmh : config/lvmh.json
with org as (
  select id from public.organisations where nom = 'Youno' order by cree_le, id limit 1
)
insert into public.groupes (organisation_id, tete_siren, nom)
select org.id, '775670417', 'LVMH' from org
on conflict (organisation_id, tete_siren) do nothing;

with g as (
  select g.id, g.organisation_id
  from public.groupes g
  where g.tete_siren = '775670417'
    and g.organisation_id = (
      select id from public.organisations where nom = 'Youno' order by cree_le, id limit 1
    )
)
insert into public.reglages (groupe_id, organisation_id, version, contenu, origine, valide_le)
select g.id, g.organisation_id, 1, $r0${
  "groupe": "LVMH",
  "tete": "775670417",
  "marques_sures": [
    "LVMH",
    "Moet Hennessy",
    "Louis Vuitton",
    "Christian Dior Couture",
    "Parfums Christian Dior",
    "Veuve Clicquot",
    "Moet & Chandon",
    "Moet et Chandon",
    "Jas Hennessy",
    "Dom Perignon",
    "MHCS",
    "M H C S",
    "Loro Piana",
    "Rimowa",
    "TAG Heuer",
    "Make Up For Ever",
    "Acqua di Parma",
    "Maison Francis Kurkdjian",
    "Parfum Francis Kurkdjian",
    "Yquem",
    "Chateau d Yquem",
    "Clos des Lambrays",
    "Domaine des Lambrays",
    "Chateau Galoupet",
    "Chateau d Esclans",
    "Sephora",
    "Belmond"
  ],
  "marques_ambigues": [
    "Celine",
    "Kenzo",
    "Givenchy",
    "Guerlain",
    "Fred",
    "Tiffany",
    "Krug",
    "Ruinart",
    "Mercier",
    "Chandon",
    "Chaumet",
    "Berluti",
    "Loewe",
    "Fendi",
    "Patou",
    "Moynat",
    "Zenith",
    "Hublot",
    "Benefit",
    "Fresh",
    "Belvedere",
    "Le Bon Marche",
    "La Samaritaine",
    "La Grande Epicerie",
    "Cheval Blanc",
    "Chateau Cheval Blanc",
    "Les Echos",
    "Le Parisien",
    "Radio Classique",
    "Tanneries Roux",
    "DFS",
    "Starboard",
    "Repossi",
    "Bulgari",
    "Marc Jacobs",
    "Pucci",
    "Galliano",
    "Minuty",
    "White 1921",
    "Jardin d Acclimatation",
    "Christian Dior",
    "Dior",
    "Hennessy",
    "Moet",
    "Parfums Givenchy",
    "Ufipar",
    "Sofidiv",
    "Eutrope"
  ],
  "exclus": [
    "582110987",
    "775625767",
    "314685454"
  ],
  "familles_exclues": [
    "ARNAULT"
  ],
  "marques_sures_homonymes": [
    "SEPHORA",
    "BELMOND",
    "YQUEM"
  ],
  "priorite": [
    "338228414"
  ],
  "exclus_noms": [
    "AGLAE"
  ],
  "marques_sigles": [
    "LVMH",
    "MHCS",
    "M H C S"
  ],
  "organigramme": [
    "Moet Hennessy",
    "Louis Vuitton Malletier",
    "Christian Dior Couture",
    "Parfums Christian Dior",
    "Celine",
    "Fendi",
    "Givenchy",
    "Kenzo",
    "Loewe",
    "Berluti",
    "Loro Piana",
    "Moynat",
    "Jean Patou",
    "Emilio Pucci",
    "Marc Jacobs",
    "Rimowa",
    "Guerlain",
    "Benefit Cosmetics",
    "Fresh SAS",
    "Make Up For Ever",
    "Acqua di Parma",
    "Parfum Francis Kurkdjian",
    "Bulgari",
    "Tiffany",
    "TAG Heuer",
    "Hublot",
    "Chaumet",
    "Fred",
    "Repossi",
    "Sephora",
    "Le Bon Marche",
    "Samaritaine",
    "Chateau Cheval Blanc",
    "Les Echos",
    "Le Parisien",
    "Radio Classique",
    "Minuty",
    "Chandon International",
    "Chateau du Galoupet",
    "Chateau d Esclans",
    "Krug Vins Fins de Champagne",
    "Ruinart",
    "Veuve Clicquot",
    "Jas Hennessy",
    "Cova France",
    "Tanneries Roux",
    "White 1921"
  ]
}$r0$::jsonb, 'depart', now() from g
on conflict (groupe_id, version) do nothing;

-- vinci : config/vinci.json
with org as (
  select id from public.organisations where nom = 'Youno' order by cree_le, id limit 1
)
insert into public.groupes (organisation_id, tete_siren, nom)
select org.id, '552037806', 'VINCI' from org
on conflict (organisation_id, tete_siren) do nothing;

with g as (
  select g.id, g.organisation_id
  from public.groupes g
  where g.tete_siren = '552037806'
    and g.organisation_id = (
      select id from public.organisations where nom = 'Youno' order by cree_le, id limit 1
    )
)
insert into public.reglages (groupe_id, organisation_id, version, contenu, origine, valide_le)
select g.id, g.organisation_id, 1, $r0${
  "groupe": "VINCI",
  "tete": "552037806",
  "marques_sures": [
    "VINCI",
    "Eurovia",
    "Actemium",
    "Axians",
    "Omexom",
    "Cegelec",
    "Soletanche Bachy",
    "Soletanche",
    "Bachy Soletanche",
    "Cofiroute",
    "ASF",
    "Autoroutes du Sud de la France",
    "Escota",
    "Arcour",
    "Sogea",
    "Dodin Campenon Bernard",
    "Campenon Bernard",
    "GTM Batiment",
    "GTM Hallé",
    "Chantiers Modernes",
    "Botte Fondations",
    "Botte Sondages",
    "Terrasol",
    "Sixense",
    "Nuvia",
    "Entrepose",
    "Vinci Immobilier",
    "Vinci Construction",
    "Vinci Energies",
    "Vinci Autoroutes",
    "Vinci Airports",
    "Vinci Concessions",
    "Vinci Facilities",
    "Vinci Railways",
    "Vinci Stadium",
    "Vinci Highways",
    "Citeos",
    "Graniou ATEM",
    "Santerne",
    "Fournie Grospaud",
    "Spark",
    "Getelec",
    "Lefort Francheteau",
    "Petitjean",
    "Moter",
    "Hydrokarst"
  ],
  "marques_ambigues": [
    "Freyssinet",
    "Menard",
    "Graniou",
    "GTM",
    "Sogetrel",
    "Masse",
    "Jean Lefebvre",
    "Carrieres",
    "Signature",
    "Sotrame",
    "Socaso",
    "Eurovia Grands Travaux",
    "Mesa",
    "Cari",
    "Bateg",
    "Dumez",
    "Tunzini",
    "Faceo",
    "Nord France",
    "Lyon Aeroports",
    "Aeroports de Lyon",
    "Aeroport de Nantes",
    "Aeroports du Grand Ouest",
    "Stade de France",
    "Consortium Stade de France"
  ],
  "exclus": [],
  "familles_exclues": [],
  "marques_sures_homonymes": [
    "ASF",
    "CITEOS",
    "MOTER",
    "PETITJEAN",
    "SANTERNE",
    "SPARK",
    "VINCI"
  ],
  "priorite": [
    "348866260",
    "391635844"
  ],
  "marques_sigles": [],
  "organigramme": [
    "VINCI Construction",
    "VINCI Construction France",
    "VINCI Construction Grands Projets",
    "VINCI Energies",
    "VINCI Energies France",
    "VINCI Autoroutes",
    "VINCI Airports",
    "VINCI Concessions",
    "VINCI Immobilier",
    "VINCI Immobilier Promotion",
    "Autoroutes du Sud de la France",
    "Cofiroute",
    "Escota",
    "Arcour",
    "Eurovia",
    "Soletanche Bachy France",
    "Soletanche Bachy International",
    "Freyssinet France",
    "Menard",
    "Sixense",
    "Nuvia",
    "Entrepose Contracting",
    "Cegelec",
    "Axians",
    "Actemium",
    "Omexom",
    "Citeos",
    "Sogea Satom",
    "Dodin Campenon Bernard",
    "Chantiers Modernes Construction",
    "GTM Batiment",
    "VINCI Facilities",
    "VINCI Railways",
    "Consortium Stade de France",
    "Aeroports de Lyon",
    "Aeroports du Grand Ouest",
    "VINCI Stadium"
  ]
}$r0$::jsonb, 'depart', now() from g
on conflict (groupe_id, version) do nothing;
