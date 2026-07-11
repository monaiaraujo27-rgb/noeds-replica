-- ============================================================
-- Projeto Supabase "SETUP" (ref cvzaqqlagwueldpookdf)
-- Tabela do FORMULÁRIO DO CLIENTE (réplica do dossier.noeds.com.br)
-- O cliente recebe um link + código (MKT@2026), preenche as 7 seções,
-- e as respostas ficam aqui. A equipe lê no "Banco de clientes".
--
-- Padrão de segurança validado (Odara/Noeds):
--   anon INSERE e faz UPSERT do próprio registro (por id do link);
--   leitura só via RPC get_respostas(token). Publishable key NÃO lê direto.
--   UPSERT usa Prefer: return=minimal (evita 42501 no SELECT pós-insert).
-- ============================================================

-- 1) Tabela: cada linha = um cliente/link
create table if not exists public.dossie_respostas (
  id            text primary key,               -- id do link (ex.: dossie-<rand>)
  created_at    timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  clinica       text not null default '',       -- nome (preenchido na 1ª seção)
  responsavel   text not null default '',
  modelo        text not null default 'clinica',
  status        text not null default 'nao-iniciado',  -- nao-iniciado | andamento | concluido
  progresso     int  not null default 0,               -- 0..100
  dados         jsonb not null default '{}'::jsonb      -- 8 blocos: empresa, posicionamento, publico, oferta, comercial, marketing, crescimento, arquivos
);

-- 2) RLS ligado
alter table public.dossie_respostas enable row level security;

-- 3) anon pode INSERIR (criar o link) — checagem mínima
drop policy if exists "anon insert resposta" on public.dossie_respostas;
create policy "anon insert resposta"
  on public.dossie_respostas for insert to anon
  with check ( char_length(coalesce(id,'')) > 4 );

-- 4) anon pode ATUALIZAR o próprio registro (autosave do formulário).
--    Sem SELECT para anon; o app faz UPDATE por id conhecido (do link) e
--    usa Prefer: return=minimal.
drop policy if exists "anon update resposta" on public.dossie_respostas;
create policy "anon update resposta"
  on public.dossie_respostas for update to anon
  using ( true )
  with check ( true );

-- 5) Leitura só via RPC com token (mesmo token do get_clientes).
drop function if exists public.get_respostas(text);
create or replace function public.get_respostas(token text)
returns setof public.dossie_respostas
language plpgsql
security definer
set search_path = ''
as $$
begin
  if token <> 'dossie_4df5b2433df2f1cffee71b22' then
    raise exception 'unauthorized';
  end if;
  return query
    select * from public.dossie_respostas order by atualizado_em desc;
end;
$$;

revoke all on function public.get_respostas(text) from public;
grant execute on function public.get_respostas(text) to anon;

-- 6) RPC para o FORMULÁRIO ler o próprio registro (por id) sem token de equipe.
--    Necessário para retomar o preenchimento (autosave). Retorna 1 linha por id.
drop function if exists public.get_resposta_by_id(rid text);
create or replace function public.get_resposta_by_id(rid text)
returns setof public.dossie_respostas
language plpgsql
security definer
set search_path = ''
as $$
begin
  return query
    select * from public.dossie_respostas where id = rid limit 1;
end;
$$;

revoke all on function public.get_resposta_by_id(text) from public;
grant execute on function public.get_resposta_by_id(text) to anon;

-- pronto.
