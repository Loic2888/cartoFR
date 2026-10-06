"""Construit data/sieges.parquet : le siège actif de chaque personne morale active, avec une clé d'adresse normalisée."""
import duckdb
c = duckdb.connect()
c.sql("""
copy (
  select e.siren, e.siren || e.nic siret_siege,
         upper(trim(coalesce(e.numeroVoieEtablissement,'') || coalesce(e.indiceRepetitionDernierNumeroVoieEtablissement,''))) num,
         upper(coalesce(e.typeVoieEtablissement,'')) type_voie, upper(coalesce(e.libelleVoieEtablissement,'')) voie,
         e.codePostalEtablissement cp, e.libelleCommuneEtablissement commune,
         upper(trim(coalesce(e.numeroVoieEtablissement,'') || ' ' || coalesce(e.typeVoieEtablissement,'') || ' ' || coalesce(e.libelleVoieEtablissement,'') || ' ' || coalesce(e.codePostalEtablissement,''))) adresse_cle,
         u.denominationUniteLegale nom, u.categorieJuridiqueUniteLegale cj, u.activitePrincipaleUniteLegale naf, u.trancheEffectifsUniteLegale tranche
  from 'data/etablissement.parquet' e join 'data/unite_legale.parquet' u using (siren)
  where e.etablissementSiege and e.etatAdministratifEtablissement = 'A'
    and u.etatAdministratifUniteLegale = 'A' and u.categorieJuridiqueUniteLegale <> 1000
) to 'data/sieges.parquet' (format parquet)
""")
print(c.sql("select count(*) from 'data/sieges.parquet'").fetchall())
