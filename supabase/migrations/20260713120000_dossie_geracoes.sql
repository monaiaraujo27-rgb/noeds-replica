-- ============================================================
-- Level 4.6: versionamento de gerações.
-- Hoje "Salvar e finalizar" sobrescreve dossie_clientes.documentos — cada
-- nova geração apaga a anterior sem deixar rastro. Esta tabela guarda uma
-- linha por geração salva, sem nunca sobrescrever: histórico completo por
-- cliente. dossie_clientes.documentos continua existindo como CACHE da
-- versão atual (é o que build.py/RENDER_JS já leem — não muda esse lado).
-- Mesmo padrão RPC security definer + auth.uid() contra team_members já
-- usado no projeto (ver 20260711180000_auth_rpcs.sql).
-- ============================================================

create table if not exists public.dossie_geracoes (
  id          uuid primary key default gen_random_uuid(),
  cliente_id  uuid not null references public.dossie_clientes(id) on delete cascade,
  criado_em   timestamptz not null default now(),
  criado_por  uuid references auth.users(id),
  documentos  jsonb not null default '{}'::jsonb
);

create index if not exists dossie_geracoes_cliente_id_idx
  on public.dossie_geracoes (cliente_id, criado_em desc);

alter table public.dossie_geracoes enable row level security;

-- só a equipe autenticada lê/grava (mesmo padrão de dossie_clientes: anon
-- nunca acessa esta tabela diretamente, tudo passa por RPC security definer).

create or replace function public.get_geracoes_auth(p_cliente_id uuid)
returns setof public.dossie_geracoes
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid()) then
    raise exception 'unauthorized';
  end if;
  return query
    select * from public.dossie_geracoes
    where cliente_id = p_cliente_id
    order by criado_em desc;
end;
$$;
revoke all on function public.get_geracoes_auth(uuid) from public;
grant execute on function public.get_geracoes_auth(uuid) to authenticated;

create or replace function public.criar_geracao_auth(p_cliente_id uuid, p_documentos jsonb)
returns public.dossie_geracoes
language plpgsql
security definer
set search_path = ''
as $$
declare
  nova public.dossie_geracoes;
begin
  if not exists (select 1 from public.team_members where id = auth.uid()) then
    raise exception 'unauthorized';
  end if;
  insert into public.dossie_geracoes (cliente_id, criado_por, documentos)
  values (p_cliente_id, auth.uid(), p_documentos)
  returning * into nova;
  return nova;
end;
$$;
revoke all on function public.criar_geracao_auth(uuid, jsonb) from public;
grant execute on function public.criar_geracao_auth(uuid, jsonb) to authenticated;

-- pronto.
