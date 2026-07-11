-- remove o registro antigo da Sorriso e Cia sem documentos (pré-feature)
delete from public.dossie_clientes
  where upper(clinica) like 'SORRISO E CIA%' and (documentos is null or documentos = '{}'::jsonb);
