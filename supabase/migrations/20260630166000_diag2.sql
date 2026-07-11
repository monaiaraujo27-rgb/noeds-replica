create or replace function public.list_pol()
returns json language sql security definer set search_path='' as $$
  select coalesce(json_agg(json_build_object(
    'name',polname,'cmd',polcmd,'permissive',polpermissive,
    'roles',polroles::regrole[]::text[],
    'check',pg_get_expr(polwithcheck,polrelid),
    'using',pg_get_expr(polqual,polrelid))),'[]'::json)
  from pg_policy p join pg_class c on c.oid=p.polrelid where c.relname='dossie_clientes';
$$;
-- também confirma se RLS está habilitado e se há FORCE
create or replace function public.rls_state()
returns json language sql security definer set search_path='' as $$
  select json_build_object('relrowsecurity',c.relrowsecurity,'relforcerowsecurity',c.relforcerowsecurity)
  from pg_class c where c.relname='dossie_clientes' and c.relnamespace='public'::regnamespace;
$$;
grant execute on function public.list_pol() to public;
grant execute on function public.rls_state() to public;
notify pgrst, 'reload schema';
