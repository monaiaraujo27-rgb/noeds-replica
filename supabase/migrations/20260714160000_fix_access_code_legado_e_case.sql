-- ============================================================
-- Achados de uma segunda rodada de revisão (2026-07-14) sobre a correção
-- anterior (20260714130000_fix_access_code_leak.sql):
--
-- 1) ALTA: upsert_resposta era fail-open pra registros LEGADOS sem
--    access_code (criados antes da coluna existir — confirmado em
--    produção, gen_app.py:2019 mostra "(sem código — registro antigo)").
--    `select access_code into existente` retorna NULL tanto quando a
--    linha não existe (INSERT novo, ok) quanto quando ela existe mas o
--    access_code é NULL (registro legado) — a guarda antiga
--    "existente is not null and ..." tratava os dois casos como iguais e
--    deixava o registro legado ser sobrescrito por QUALQUER chamada
--    anônima, sem exigir nenhum código. Corrigido usando FOUND (diferencia
--    "0 linhas" de "1 linha com valor NULL"): registro legado agora fica
--    bloqueado pra update até a equipe regularizar (ver função nova
--    abaixo), igual a qualquer outro cliente sem o código certo.
--
-- 2) MÉDIA: check_access_code (usada tanto no portão do cliente quanto em
--    checarEquipe()) continuava case-sensitive enquanto get_resposta_by_id/
--    upsert_resposta já comparam via upper(). O portão do cliente
--    (showGate) não sofre na prática porque já normaliza o input antes de
--    enviar, mas checarEquipe() (fluxo "&equipe=1&cod=...", usado quando a
--    equipe edita a URL manualmente) não normalizava — código digitado em
--    minúsculo falhava silenciosamente ali. Corrigido: check_access_code
--    agora compara via upper() também.
--
-- 3) Registros legados sem access_code ficam bloqueados pra sempre sem uma
--    forma de regularizar — cria-se regenerar_access_code_auth (só
--    equipe autenticada) pra definir/trocar o código de um cliente já
--    existente, cobrindo tanto "regularizar legado" quanto "cliente
--    perdeu o código e precisa de um novo".
-- ============================================================

create or replace function public.check_access_code(rid text, code text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  ok boolean;
begin
  select (access_code is not null and upper(access_code) = upper(coalesce(code,''))) into ok
  from public.dossie_respostas where id = rid;
  return coalesce(ok, false);
end;
$$;
revoke all on function public.check_access_code(text, text) from public;
grant execute on function public.check_access_code(text, text) to anon;

create or replace function public.upsert_resposta(
  rid text,
  p_clinica text,
  p_responsavel text,
  p_status text,
  p_progresso int,
  p_dados jsonb,
  p_modelo text default null,
  p_access_code text default null,
  p_access_code_atual text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  existente text;
begin
  if char_length(coalesce(rid,'')) < 5 then
    raise exception 'invalid id';
  end if;
  if octet_length(coalesce(p_dados,'{}'::jsonb)::text) > 500000 then
    raise exception 'dados excedem o tamanho máximo permitido';
  end if;

  select access_code into existente from public.dossie_respostas where id = rid;

  -- FOUND é true quando a linha existe (mesmo com access_code NULL) e
  -- false quando não existe nenhuma linha com esse id — diferente de
  -- checar "existente is not null", que não distingue os dois casos.
  -- Registro legado (existe, access_code NULL) cai aqui e é bloqueado,
  -- porque nenhum p_access_code_atual pode ser igual a NULL.
  if FOUND and upper(coalesce(existente, chr(1))) <> upper(coalesce(p_access_code_atual, chr(2))) then
    raise exception 'unauthorized';
  end if;

  insert into public.dossie_respostas (id, clinica, responsavel, status, progresso, dados, modelo, access_code, atualizado_em)
    values (rid, coalesce(p_clinica,''), coalesce(p_responsavel,''),
            coalesce(p_status,'nao-iniciado'), coalesce(p_progresso,0),
            coalesce(p_dados,'{}'::jsonb), coalesce(nullif(p_modelo,''),'clinica'), nullif(p_access_code,''), now())
  on conflict (id) do update set
    clinica       = excluded.clinica,
    responsavel   = excluded.responsavel,
    status        = excluded.status,
    progresso     = excluded.progresso,
    dados         = excluded.dados,
    modelo        = coalesce(nullif(p_modelo,''), public.dossie_respostas.modelo),
    access_code   = coalesce(nullif(p_access_code,''), public.dossie_respostas.access_code),
    atualizado_em = now();
end;
$$;
revoke all on function public.upsert_resposta(text, text, text, text, int, jsonb, text, text, text) from public;
grant execute on function public.upsert_resposta(text, text, text, text, int, jsonb, text, text, text) to anon;

-- regulariza/troca o código de acesso de um cliente já existente — só
-- equipe autenticada (mesmo padrão de delete_resposta_auth/set_share_token_auth).
create or replace function public.regenerar_access_code_auth(rid text, novo_codigo text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid()) then
    raise exception 'unauthorized';
  end if;
  if char_length(coalesce(novo_codigo,'')) < 4 then
    raise exception 'código muito curto';
  end if;
  update public.dossie_respostas set access_code = novo_codigo where id = rid;
end;
$$;
revoke all on function public.regenerar_access_code_auth(text, text) from public;
grant execute on function public.regenerar_access_code_auth(text, text) to authenticated;

-- pronto.
