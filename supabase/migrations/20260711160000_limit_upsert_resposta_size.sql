-- ============================================================
-- Achado MÉDIO da auditoria (2026-07-11): upsert_resposta aceitava p_dados
-- jsonb sem limite de tamanho algum. maxlength foi adicionado nos campos do
-- formulário (client-side, gen_form.py), mas isso não protege contra uma
-- chamada direta ao RPC via REST (bypass trivial do client). Reforço aqui
-- no servidor: rejeita p_dados acima de 500KB serializado — bem acima de
-- qualquer preenchimento legítimo dos ~100 campos do formulário (mesmo
-- todos no limite de 4000 chars cada, o total fica na casa de dezenas de
-- KB), mas barra abuso deliberado (payload gigante inflando custo de
-- armazenamento e, principalmente, custo de tokens quando a equipe gera o
-- dossiê por IA usando esse texto como contexto do prompt).
-- ============================================================

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
  if octet_length(coalesce(p_dados,'{}'::jsonb)::text) > 500000 then
    raise exception 'dados excedem o tamanho máximo permitido';
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
    modelo        = coalesce(nullif(p_modelo,''), public.dossie_respostas.modelo),
    atualizado_em = now();
end;
$$;

revoke all on function public.upsert_resposta(text, text, text, text, int, jsonb, text) from public;
grant execute on function public.upsert_resposta(text, text, text, text, int, jsonb, text) to anon;

-- pronto.
