-- PostgREST exige GRANT de tabela ALÉM da policy RLS. Provavelmente anon não tem INSERT grant.
grant insert on table public.dossie_clientes to anon;
grant select on table public.dossie_clientes to anon;  -- RLS ainda bloqueia select (sem policy select), mas grant é necessário p/ retorno
notify pgrst, 'reload schema';
