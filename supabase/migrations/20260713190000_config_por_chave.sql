-- ============================================================
-- Generaliza app_config pra guardar mais de 1 configuração (antes só o
-- prompt de geração). Agora também guarda o PMI (Plano de Marketing
-- Inteligente) fixo, colado 1 vez e reaproveitado igual em todo cliente
-- novo — deixa de ser gerado por IA a cada dossiê.
--
-- Troca os RPCs de chave fixa (get/set_prompt_config_auth) por versões
-- parametrizadas por chave, com allowlist (evita escrita em chave
-- arbitrária). Mesmas trava de autorização: leitura qualquer
-- authenticated, escrita só admin.
-- ============================================================

drop function if exists public.get_prompt_config_auth();
drop function if exists public.set_prompt_config_auth(text);

create or replace function public.get_config_auth(p_chave text)
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
  if p_chave not in ('prompt_geracao', 'pmi_conteudo') then
    raise exception 'chave inválida';
  end if;
  select valor into v from public.app_config where chave = p_chave;
  return v;
end;
$$;
revoke all on function public.get_config_auth(text) from public;
grant execute on function public.get_config_auth(text) to authenticated;

create or replace function public.set_config_auth(p_chave text, novo_valor text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid() and papel = 'admin') then
    raise exception 'unauthorized';
  end if;
  if p_chave not in ('prompt_geracao', 'pmi_conteudo') then
    raise exception 'chave inválida';
  end if;
  insert into public.app_config (chave, valor, atualizado_em, atualizado_por)
  values (p_chave, novo_valor, now(), auth.uid())
  on conflict (chave) do update
    set valor = excluded.valor, atualizado_em = now(), atualizado_por = auth.uid();
end;
$$;
revoke all on function public.set_config_auth(text, text) from public;
grant execute on function public.set_config_auth(text, text) to authenticated;

-- pronto.
