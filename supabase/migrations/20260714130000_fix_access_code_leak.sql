-- ============================================================
-- CRÍTICO — Achado em varredura de segurança (2026-07-14): o "portão de
-- código" do formulário público (dossie.html) era só uma barreira de UI.
-- Os dois RPCs que o formulário realmente usa para ler/escrever dados
-- (get_resposta_by_id, upsert_resposta) nunca validavam o access_code —
-- só exigiam o `rid` (o id do link, que trafega em texto plano na própria
-- URL enviada ao cliente por WhatsApp/e-mail, podendo vazar por
-- encaminhamento, print, histórico de navegador compartilhado etc).
--
-- Confirmado em produção: uma chamada anônima a get_resposta_by_id com
-- apenas o rid de um cliente retornou TODAS as respostas dele, incluindo
-- o próprio access_code em texto plano — sem nunca ter passado pelo
-- portão. upsert_resposta tinha o mesmo problema: sobrescrevia as
-- respostas de qualquer cliente conhecendo só o rid, sem o código.
--
-- Correção: as duas funções agora exigem o access_code do cliente.
--   - get_resposta_by_id(rid, code): só retorna a linha se code bater
--     (comparação case-insensitive — ver também a migration de
--     normalização do código). Deixa de fazer "select *": retorna uma
--     projeção explícita SEM a coluna access_code, então mesmo com o
--     código correto o valor nunca volta ao client novamente.
--   - upsert_resposta(..., p_access_code_atual): em UPDATE (linha já
--     existe), exige que p_access_code_atual bata com o access_code
--     salvo. Em INSERT (linha nova — criação do cliente pela equipe,
--     que já define o access_code na criação via p_access_code) não há
--     código anterior para validar, então o INSERT segue livre (mesmo
--     comportamento de hoje) — mas isso só cria linhas novas, nunca
--     sobrescreve uma existente sem o código certo.
--
-- Compatibilidade: gen_app.py (equipe, cria clientes) sempre envia
-- p_access_code (o código que acabou de gerar) e nunca teve um
-- access_code_atual anterior por não fazer update de resposta de
-- cliente já existente por esse caminho — não quebra o painel interno.
-- gen_form.py (formulário do cliente) precisa passar a guardar o código
-- validado em memória (não mais só um flag booleano) e reenviá-lo em
-- toda chamada de load/save — ver mudanças em gen_form.py no mesmo
-- commit.
-- ============================================================

drop function if exists public.get_resposta_by_id(rid text);
create or replace function public.get_resposta_by_id(rid text, code text)
returns table (
  id text, created_at timestamptz, atualizado_em timestamptz,
  clinica text, responsavel text, modelo text, status text,
  progresso int, dados jsonb
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  return query
    select d.id, d.created_at, d.atualizado_em, d.clinica, d.responsavel,
           d.modelo, d.status, d.progresso, d.dados
    from public.dossie_respostas d
    where d.id = rid
      and d.access_code is not null
      and upper(d.access_code) = upper(coalesce(code,''))
    limit 1;
end;
$$;
revoke all on function public.get_resposta_by_id(text, text) from public;
grant execute on function public.get_resposta_by_id(text, text) to anon;

drop function if exists public.upsert_resposta(text, text, text, text, int, jsonb, text, text);
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

  -- linha já existe e tem código definido: só atualiza se o código
  -- informado bater (impede sobrescrever resposta de outro cliente
  -- conhecendo só o rid).
  if existente is not null and upper(existente) <> upper(coalesce(p_access_code_atual,'')) then
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

-- pronto.
