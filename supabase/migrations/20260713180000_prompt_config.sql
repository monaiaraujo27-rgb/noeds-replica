-- ============================================================
-- Prompt de geração editável pela equipe (botão "Prompt de geração" em
-- gerar.html, que hoje só mostra o texto fixo do código em modo leitura).
-- Guarda 1 linha só (chave fixa "prompt_geracao") com o texto-base
-- customizado; NULL/ausente = usa o padrão embutido no código
-- (_montarPromptDoc). Compartilhado por toda a equipe (mesmo modelo de
-- "todo autenticado vê tudo" já usado no resto do projeto).
--
-- Leitura: qualquer autenticado (precisa carregar o valor atual pra
-- editar/gerar). Escrita: só admin — afeta a geração de TODA a equipe,
-- mesma trava já usada em set_share_token_auth/delete_resposta_auth.
-- ============================================================

create table if not exists public.app_config (
  chave text primary key,
  valor text,
  atualizado_em timestamptz not null default now(),
  atualizado_por uuid references auth.users(id)
);

alter table public.app_config enable row level security;

create or replace function public.get_prompt_config_auth()
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v text;
begin
  if auth.uid() is null then
    raise exception 'unauthorized';
  end if;
  select valor into v from public.app_config where chave = 'prompt_geracao';
  return v;
end;
$$;
revoke all on function public.get_prompt_config_auth() from public;
grant execute on function public.get_prompt_config_auth() to authenticated;

create or replace function public.set_prompt_config_auth(novo_valor text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid() and papel = 'admin') then
    raise exception 'unauthorized';
  end if;
  insert into public.app_config (chave, valor, atualizado_em, atualizado_por)
  values ('prompt_geracao', novo_valor, now(), auth.uid())
  on conflict (chave) do update
    set valor = excluded.valor, atualizado_em = now(), atualizado_por = auth.uid();
end;
$$;
revoke all on function public.set_prompt_config_auth(text) from public;
grant execute on function public.set_prompt_config_auth(text) to authenticated;

-- pronto.
