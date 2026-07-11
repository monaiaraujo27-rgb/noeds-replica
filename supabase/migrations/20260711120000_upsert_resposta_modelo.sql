-- ============================================================
-- Adiciona o parâmetro p_modelo ao upsert_resposta para persistir o
-- TIPO de dossiê (clinica | servicos | produtos) na coluna `modelo`
-- (que já existe na tabela, default 'clinica', mas era ignorada pelo RPC).
-- Compat: se p_modelo vier null/'', preserva o valor atual (não sobrescreve).
-- ============================================================

drop function if exists public.upsert_resposta(text, text, text, text, int, jsonb);
drop function if exists public.upsert_resposta(text, text, text, text, int, jsonb, text);
create or replace function public.upsert_resposta(
  rid text,
  p_clinica text,
  p_responsavel text,
  p_status text,
  p_progresso int,
  p_dados jsonb,
  p_modelo text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if char_length(coalesce(rid,'')) < 5 then
    raise exception 'invalid id';
  end if;
  insert into public.dossie_respostas (id, clinica, responsavel, status, progresso, dados, modelo, atualizado_em)
    values (rid, coalesce(p_clinica,''), coalesce(p_responsavel,''),
            coalesce(p_status,'nao-iniciado'), coalesce(p_progresso,0),
            coalesce(p_dados,'{}'::jsonb), coalesce(nullif(p_modelo,''),'clinica'), now())
  on conflict (id) do update set
    clinica       = excluded.clinica,
    responsavel   = excluded.responsavel,
    status        = excluded.status,
    progresso     = excluded.progresso,
    dados         = excluded.dados,
    -- só troca o modelo se um valor não-vazio foi informado; senão mantém o atual
    modelo        = coalesce(nullif(p_modelo,''), public.dossie_respostas.modelo),
    atualizado_em = now();
end;
$$;

revoke all on function public.upsert_resposta(text, text, text, text, int, jsonb, text) from public;
grant execute on function public.upsert_resposta(text, text, text, text, int, jsonb, text) to anon;
