-- ============================================================
-- Projeto Supabase "Dossie" — schema do Banco de clientes
-- Rode no SQL Editor do projeto novo. Mesmo padrão de segurança
-- validado no projeto Odara: anon só INSERE; leitura via RPC + token.
-- ============================================================

-- 1) Tabela
create table if not exists public.dossie_clientes (
  id              uuid primary key default gen_random_uuid(),
  created_at      timestamptz not null default now(),
  clinica         text not null,
  dados           jsonb not null default '{}'::jsonb,   -- campos estruturados pela IA
  respostas_brutas text                                 -- texto colado original
);

-- 2) RLS ligado
alter table public.dossie_clientes enable row level security;

-- 3) anon pode INSERIR (com checagem mínima), mas NÃO pode SELECT
drop policy if exists "anon insert dossie" on public.dossie_clientes;
create policy "anon insert dossie"
  on public.dossie_clientes for insert to anon
  with check ( char_length(coalesce(clinica,'')) > 0 );

-- 4) Leitura só via RPC com token (publishable key não lê a tabela direto)
--    Troque o token abaixo por um seu (segredo). Ele fica no painel (localStorage).
create or replace function public.get_clientes(token text)
returns setof public.dossie_clientes
language plpgsql
security definer
set search_path = ''
as $$
begin
  if token <> 'dossie_4df5b2433df2f1cffee71b22' then
    raise exception 'unauthorized';
  end if;
  return query
    select * from public.dossie_clientes order by created_at desc;
end;
$$;

revoke all on function public.get_clientes(text) from public;
grant execute on function public.get_clientes(text) to anon;

-- pronto. Anote: URL do projeto, publishable key, e o token acima.
