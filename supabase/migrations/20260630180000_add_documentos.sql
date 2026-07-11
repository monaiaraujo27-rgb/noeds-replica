-- guarda o JSON dos 9 documentos gerados por IA para cada cliente
alter table public.dossie_clientes add column if not exists documentos jsonb default '{}'::jsonb;
notify pgrst, 'reload schema';
