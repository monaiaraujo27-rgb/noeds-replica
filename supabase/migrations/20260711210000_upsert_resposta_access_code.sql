-- ============================================================
-- Adiciona p_access_code (opcional) ao upsert_resposta, seguindo o mesmo
-- padrão de compatibilidade do p_modelo: só grava se vier não-vazio,
-- senão preserva o valor atual — assim o autosave do formulário (que
-- nunca envia esse parâmetro) nunca apaga o código gerado na criação.
-- ============================================================

drop function if exists public.upsert_resposta(text, text, text, text, int, jsonb, text);
create or replace function public.upsert_resposta(
  rid text,
  p_clinica text,
  p_responsavel text,
  p_status text,
  p_progresso int,
  p_dados jsonb,
  p_modelo text default null,
  p_access_code text default null
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

revoke all on function public.upsert_resposta(text, text, text, text, int, jsonb, text, text) from public;
grant execute on function public.upsert_resposta(text, text, text, text, int, jsonb, text, text) to anon;

-- pronto.
