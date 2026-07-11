-- ============================================================
-- Level 3: RPCs autenticados substituindo os baseados em token hardcoded.
-- Mesmo padrão RPC security definer já usado no projeto — só troca a fonte
-- de autorização de "token em texto" para "sessão JWT via auth.uid()".
--
-- get_clientes(token)/get_respostas(token)/delete_resposta(rid,token) e
-- set_share_token(cliente_id,novo_token,token) continuam existindo por ora
-- (não removidos ainda — só descomissionados no client em 20260711180000+
-- do código, e podem ser dropados numa migration futura depois de
-- confirmar que nada mais os chama). Os novos RPCs abaixo são _auth,
-- checam auth.uid() contra team_members, e serão os únicos usados pelo
-- client a partir de agora.
-- ============================================================

create or replace function public.get_clientes_auth()
returns setof public.dossie_clientes
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid()) then
    raise exception 'unauthorized';
  end if;
  return query
    select * from public.dossie_clientes order by created_at desc;
end;
$$;
revoke all on function public.get_clientes_auth() from public;
grant execute on function public.get_clientes_auth() to authenticated;

create or replace function public.get_respostas_auth()
returns setof public.dossie_respostas
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid()) then
    raise exception 'unauthorized';
  end if;
  return query
    select * from public.dossie_respostas order by atualizado_em desc;
end;
$$;
revoke all on function public.get_respostas_auth() from public;
grant execute on function public.get_respostas_auth() to authenticated;

create or replace function public.delete_resposta_auth(rid text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid()) then
    raise exception 'unauthorized';
  end if;
  delete from public.dossie_respostas where id = rid;
end;
$$;
revoke all on function public.delete_resposta_auth(text) from public;
grant execute on function public.delete_resposta_auth(text) to authenticated;

create or replace function public.set_share_token_auth(cliente_id uuid, novo_token text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid()) then
    raise exception 'unauthorized';
  end if;
  update public.dossie_clientes
  set share_token = novo_token
  where id = cliente_id;
end;
$$;
revoke all on function public.set_share_token_auth(uuid, text) from public;
grant execute on function public.set_share_token_auth(uuid, text) to authenticated;

-- pronto.
