create or replace function public.list_pol()
returns json language sql security definer set search_path='' as $$
  select coalesce(json_agg(json_build_object('name',polname,'cmd',polcmd,'roles',polroles::regrole[]::text[],'check',pg_get_expr(polwithcheck,polrelid))),'[]'::json)
  from pg_policy p join pg_class c on c.oid=p.polrelid where c.relname='dossie_clientes';
$$;
grant execute on function public.list_pol() to public;
notify pgrst, 'reload schema';
