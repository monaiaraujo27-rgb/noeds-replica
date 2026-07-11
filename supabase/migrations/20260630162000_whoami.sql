create or replace function public.whoami()
returns json language sql security invoker as $$
  select json_build_object('current_user', current_user, 'session_user', session_user);
$$;
grant execute on function public.whoami() to public;
