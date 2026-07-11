-- ============================================================
-- Fase 0 do roadmap level 1→5: correção de segurança urgente.
--
-- Problema 1: a policy "anon update resposta" (using(true) with check(true))
-- permite qualquer anon sobrescrever QUALQUER linha de dossie_respostas via
-- PATCH direto na tabela. O app nunca usa esse caminho — o autosave passa
-- sempre pelo RPC upsert_resposta (security definer). A policy está sobrando
-- e é pura superfície de ataque. Removida abaixo.
--
-- Problema 2: o READ_TOKEN usado por get_clientes/get_respostas/delete_resposta
-- estava compilado em texto plano no HTML publicado de clientes.html (visível
-- via "ver código-fonte"). Girado para um novo valor abaixo. Isso reduz a
-- janela de exposição mas NÃO resolve o problema estrutural — a Fase 2/3 do
-- roadmap troca esse esquema por Supabase Auth (auth.uid()) de verdade.
--
-- get_resposta_by_id(rid) continua sem token: é intencionalmente um "segredo
-- de posse" (só quem recebeu o link tem o id, que é um dossie-<rand> não
-- enumerável) — aceitável até a Fase 3 trazer verificação real via auth.uid().
-- ============================================================

-- 1) Remove a policy de UPDATE direto (autosave usa só upsert_resposta RPC).
drop policy if exists "anon update resposta" on public.dossie_respostas;

-- 2) Gira o token dos RPCs de leitura/exclusão da equipe.
--    NOVO TOKEN: dossie_c70b8dae24408ffc7b3c8bb946f81396
--    (o app precisa ser atualizado com esse valor em gen_app.py e redeployado
--    antes/junto desta migration, senão o painel para de autenticar).

drop function if exists public.get_clientes(text);
create or replace function public.get_clientes(token text)
returns setof public.dossie_clientes
language plpgsql
security definer
set search_path = ''
as $$
begin
  if token <> 'dossie_c70b8dae24408ffc7b3c8bb946f81396' then
    raise exception 'unauthorized';
  end if;
  return query
    select * from public.dossie_clientes order by created_at desc;
end;
$$;
revoke all on function public.get_clientes(text) from public;
grant execute on function public.get_clientes(text) to anon;

drop function if exists public.get_respostas(text);
create or replace function public.get_respostas(token text)
returns setof public.dossie_respostas
language plpgsql
security definer
set search_path = ''
as $$
begin
  if token <> 'dossie_c70b8dae24408ffc7b3c8bb946f81396' then
    raise exception 'unauthorized';
  end if;
  return query
    select * from public.dossie_respostas order by atualizado_em desc;
end;
$$;
revoke all on function public.get_respostas(text) from public;
grant execute on function public.get_respostas(text) to anon;

drop function if exists public.delete_resposta(text, text);
create or replace function public.delete_resposta(rid text, token text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if token <> 'dossie_c70b8dae24408ffc7b3c8bb946f81396' then
    raise exception 'unauthorized';
  end if;
  delete from public.dossie_respostas where id = rid;
end;
$$;
revoke all on function public.delete_resposta(text, text) from public;
grant execute on function public.delete_resposta(text, text) to anon;

-- pronto.
